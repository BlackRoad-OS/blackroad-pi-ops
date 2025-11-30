#!/usr/bin/env python3
"""BlackRoad Pi Agent - Main entry point.

A unified agent runtime for Raspberry Pi and other edge devices that connects
to the BlackRoad OS operator via WebSocket for task execution and telemetry.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import sys
from pathlib import Path
from typing import Optional

from .config import Config
from .connection import ConnectionManager, Message
from .executor import Executor, Task
from .scheduler import Scheduler, ScheduledTask
from .telemetry import TelemetryCollector


logger = logging.getLogger(__name__)


class PiAgent:
    """Main Pi Agent orchestrator."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self._running = False

        # Initialize components
        self.executor = Executor(config.executor)
        self.scheduler = Scheduler()
        self.telemetry = TelemetryCollector()
        self.connection = ConnectionManager(
            config=config.operator,
            agent_id=config.agent.agent_id,
            agent_type=config.agent.agent_type,
            capabilities=config.agent.capabilities,
        )

        # Register handlers
        self._setup_handlers()

    def _setup_handlers(self) -> None:
        """Set up message and task handlers."""
        # WebSocket message handlers
        self.connection.on("task", self._handle_task)
        self.connection.on("cancel", self._handle_cancel)
        self.connection.on("ping", self._handle_ping)
        self.connection.on("config", self._handle_config)

        # Scheduler callback
        self.scheduler.add_callback(self._on_scheduled_task)

    async def _handle_task(self, msg: Message) -> None:
        """Handle incoming task."""
        task = Task.from_dict(msg.payload)
        task_id = await self.executor.submit(task)
        logger.info("Started task %s", task_id)

        # Monitor task completion
        asyncio.create_task(self._monitor_task(task_id))

    async def _monitor_task(self, task_id: str) -> None:
        """Monitor task and report result."""
        while True:
            await asyncio.sleep(0.5)
            result = self.executor.get_result(task_id)
            if result and result.status.value not in ("pending", "running"):
                await self.connection.send("task_result", result.to_dict())
                logger.info("Task %s completed: %s", task_id, result.status.value)
                break

    async def _handle_cancel(self, msg: Message) -> None:
        """Handle task cancellation."""
        task_id = msg.payload.get("task_id")
        if task_id:
            cancelled = await self.executor.cancel(task_id)
            logger.info("Cancel task %s: %s", task_id, cancelled)

    async def _handle_ping(self, msg: Message) -> None:
        """Handle ping from operator."""
        await self.connection.send("pong", {
            "timestamp": msg.timestamp,
            "agent_id": self.config.agent.agent_id,
        })

    async def _handle_config(self, msg: Message) -> None:
        """Handle config update from operator."""
        logger.info("Received config update: %s", msg.payload)
        # TODO: Apply config updates

    async def _on_scheduled_task(self, scheduled: ScheduledTask) -> None:
        """Handle scheduled task execution."""
        task = Task(
            task_id=scheduled.task_id,
            task_type=scheduled.task_type,
            payload=scheduled.payload,
        )
        await self.executor.submit(task)

    async def _heartbeat_loop(self) -> None:
        """Send periodic heartbeats."""
        interval = self.config.telemetry.heartbeat_interval
        while self._running:
            try:
                if self.connection.is_connected:
                    metrics = self.telemetry.collect_metrics()
                    await self.connection.send("heartbeat", {
                        "agent_id": self.config.agent.agent_id,
                        "hostname": self.config.agent.hostname,
                        "metrics": metrics.to_dict(),
                        "running_tasks": self.executor.get_running_tasks(),
                        "scheduled_tasks": len(self.scheduler.get_scheduled_tasks()),
                    })
                    logger.debug("Sent heartbeat")
            except Exception:
                logger.exception("Error sending heartbeat")

            await asyncio.sleep(interval)

    async def start(self) -> None:
        """Start the Pi Agent."""
        logger.info("=" * 60)
        logger.info("BlackRoad Pi Agent v0.1.0")
        logger.info("=" * 60)
        logger.info("Agent ID: %s", self.config.agent.agent_id)
        logger.info("Hostname: %s", self.config.agent.hostname)
        logger.info("Agent Type: %s", self.config.agent.agent_type)
        logger.info("Capabilities: %s", ", ".join(self.config.agent.capabilities))
        logger.info("Operator URL: %s", self.config.operator.url)
        logger.info("")

        # Log system info
        sys_info = self.telemetry.get_system_info()
        logger.info("System: %s %s (%s)",
                    sys_info.get("platform"),
                    sys_info.get("platform_release"),
                    sys_info.get("architecture"))
        if "pi_model" in sys_info:
            logger.info("Pi Model: %s", sys_info.get("pi_model"))
        logger.info("")

        self._running = True

        # Start components
        await self.scheduler.start()
        await self.connection.start()

        # Start heartbeat
        heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        logger.info("Pi Agent running. Press Ctrl+C to stop.")
        logger.info("")

        try:
            # Run until stopped
            while self._running:
                await asyncio.sleep(1)
        finally:
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass

    async def stop(self) -> None:
        """Stop the Pi Agent."""
        logger.info("Stopping Pi Agent...")
        self._running = False
        await self.scheduler.stop()
        await self.connection.stop()
        logger.info("Pi Agent stopped")


def setup_logging(config: Config) -> None:
    """Configure logging."""
    log_level = getattr(logging, config.logging.level.upper(), logging.INFO)
    log_format = config.logging.format

    handlers = [logging.StreamHandler()]
    if config.logging.file:
        handlers.append(logging.FileHandler(config.logging.file))

    logging.basicConfig(
        level=log_level,
        format=log_format,
        handlers=handlers,
    )

    # Reduce noise from libraries
    logging.getLogger("websockets").setLevel(logging.WARNING)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="BlackRoad Pi Agent - Edge device runtime for BlackRoad OS"
    )
    parser.add_argument(
        "-c", "--config",
        type=Path,
        help="Path to config file",
    )
    parser.add_argument(
        "--operator-url",
        help="Override operator WebSocket URL",
    )
    parser.add_argument(
        "--agent-id",
        help="Override agent ID",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Log level",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 0.1.0",
    )
    return parser.parse_args()


async def main_async() -> int:
    """Async main entry point."""
    args = parse_args()

    # Load config
    config = Config.load(args.config)

    # Apply CLI overrides
    if args.operator_url:
        config.operator.url = args.operator_url
    if args.agent_id:
        config.agent.agent_id = args.agent_id
    if args.log_level:
        config.logging.level = args.log_level

    # Setup logging
    setup_logging(config)

    # Create and run agent
    agent = PiAgent(config)

    # Handle signals
    loop = asyncio.get_running_loop()

    def signal_handler():
        asyncio.create_task(agent.stop())

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)

    try:
        await agent.start()
        return 0
    except KeyboardInterrupt:
        await agent.stop()
        return 0
    except Exception:
        logger.exception("Fatal error")
        return 1


def main() -> None:
    """Main entry point."""
    sys.exit(asyncio.run(main_async()))


if __name__ == "__main__":
    main()
