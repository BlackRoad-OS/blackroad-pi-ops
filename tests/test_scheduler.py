"""Tests for pi_agent task scheduler."""

from __future__ import annotations

import asyncio
import pytest

from pi_agent.scheduler import Scheduler, ScheduledTask


@pytest.fixture()
async def scheduler():
    s = Scheduler()
    await s.start()
    yield s
    await s.stop()


@pytest.mark.asyncio
async def test_schedule_and_execute(scheduler):
    fired = []

    async def callback(task: ScheduledTask):
        fired.append(task.task_id)

    scheduler.add_callback(callback)
    task_id = await scheduler.schedule("shell", {"command": "echo hi"}, delay=0)

    # Wait for it to fire
    for _ in range(30):
        await asyncio.sleep(0.1)
        if fired:
            break

    assert task_id in fired


@pytest.mark.asyncio
async def test_cancel_scheduled_task(scheduler):
    fired = []

    async def callback(task: ScheduledTask):
        fired.append(task.task_id)

    scheduler.add_callback(callback)
    task_id = await scheduler.schedule("shell", {}, delay=10.0)  # far future
    cancelled = await scheduler.cancel(task_id)
    assert cancelled is True
    # Task should not fire
    await asyncio.sleep(0.2)
    assert task_id not in fired


@pytest.mark.asyncio
async def test_cancel_nonexistent_task(scheduler):
    result = await scheduler.cancel("nonexistent-id")
    assert result is False


@pytest.mark.asyncio
async def test_get_scheduled_tasks(scheduler):
    task_id = await scheduler.schedule("shell", {"k": "v"}, delay=60.0)
    tasks = scheduler.get_scheduled_tasks()
    ids = [t["task_id"] for t in tasks]
    assert task_id in ids


@pytest.mark.asyncio
async def test_reschedule(scheduler):
    task_id = await scheduler.schedule("shell", {}, delay=60.0)
    rescheduled = await scheduler.reschedule(task_id, delay=120.0)
    assert rescheduled is True
    tasks = {t["task_id"]: t for t in scheduler.get_scheduled_tasks()}
    assert task_id in tasks


@pytest.mark.asyncio
async def test_reschedule_nonexistent(scheduler):
    result = await scheduler.reschedule("no-such-task", delay=5.0)
    assert result is False


@pytest.mark.asyncio
async def test_recurring_task_fires_multiple_times(scheduler):
    fired = []

    async def callback(task: ScheduledTask):
        fired.append(task.task_id)

    scheduler.add_callback(callback)
    task_id = await scheduler.schedule("shell", {}, delay=0, repeat_interval=0.05)

    for _ in range(30):
        await asyncio.sleep(0.1)
        if len(fired) >= 2:
            break

    assert len(fired) >= 2
    await scheduler.cancel(task_id)
