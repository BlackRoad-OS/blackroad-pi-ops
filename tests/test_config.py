"""Tests for pi_agent configuration loading."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

from pi_agent.config import Config, OperatorConfig, AgentConfig, ExecutorConfig


def test_config_defaults():
    config = Config()
    assert config.operator.url == "ws://localhost:8080/ws/agent"
    assert config.agent.agent_type == "pi-node"
    assert config.executor.max_concurrent_tasks == 4
    assert config.telemetry.heartbeat_interval == 15.0
    assert config.logging.level == "INFO"


def test_config_from_dict():
    data = {
        "operator": {"url": "ws://example.com/ws", "reconnect_interval": 10.0},
        "agent": {"agent_id": "test-agent", "agent_type": "custom"},
        "executor": {"max_concurrent_tasks": 2, "task_timeout": 60.0},
        "logging": {"level": "DEBUG"},
    }
    config = Config.from_dict(data)
    assert config.operator.url == "ws://example.com/ws"
    assert config.operator.reconnect_interval == 10.0
    assert config.agent.agent_id == "test-agent"
    assert config.agent.agent_type == "custom"
    assert config.executor.max_concurrent_tasks == 2
    assert config.logging.level == "DEBUG"


def test_config_load_from_file(tmp_path):
    cfg_data = {
        "operator": {"url": "ws://file-host/ws"},
        "agent": {"agent_id": "file-agent"},
    }
    cfg_file = tmp_path / "pi-agent.config.json"
    cfg_file.write_text(json.dumps(cfg_data))

    config = Config.load(cfg_file)
    assert config.operator.url == "ws://file-host/ws"
    assert config.agent.agent_id == "file-agent"


def test_config_env_overrides(monkeypatch):
    monkeypatch.setenv("BLACKROAD_OPERATOR_URL", "ws://env-host/ws")
    monkeypatch.setenv("BLACKROAD_AGENT_ID", "env-agent")
    monkeypatch.setenv("BLACKROAD_LOG_LEVEL", "WARNING")

    config = Config._from_environment()
    assert config.operator.url == "ws://env-host/ws"
    assert config.agent.agent_id == "env-agent"
    assert config.logging.level == "WARNING"


def test_config_auto_generates_agent_id(monkeypatch):
    monkeypatch.delenv("BLACKROAD_AGENT_ID", raising=False)
    config = Config._from_environment()
    assert config.agent.agent_id != ""


def test_executor_config_blocked_commands():
    config = ExecutorConfig()
    assert "rm -rf /" in config.blocked_commands


def test_config_load_missing_file_returns_defaults():
    config = Config.load(Path("/nonexistent/path/config.json"))
    # When no explicit path exists, Config.load falls back to default search paths
    # (e.g. pi-agent.config.json in the working directory). Simply verify that
    # we get back a valid Config with a non-empty operator URL.
    assert config.operator.url != ""
