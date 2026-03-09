"""Tests for pi_agent task executor."""

from __future__ import annotations

import asyncio
import pytest

from pi_agent.config import ExecutorConfig
from pi_agent.executor import Executor, Task, TaskStatus


@pytest.fixture()
def executor():
    config = ExecutorConfig(max_concurrent_tasks=2, task_timeout=10.0)
    return Executor(config)


@pytest.mark.asyncio
async def test_execute_shell_success(executor):
    task = Task(task_id="t1", task_type="shell", payload={"command": "echo hello"})
    await executor.submit(task)
    # Wait for completion
    for _ in range(20):
        await asyncio.sleep(0.1)
        result = executor.get_result("t1")
        if result and result.status not in (TaskStatus.PENDING, TaskStatus.RUNNING):
            break
    assert result is not None
    assert result.status == TaskStatus.COMPLETED
    assert "hello" in result.stdout
    assert result.exit_code == 0


@pytest.mark.asyncio
async def test_execute_shell_failure(executor):
    task = Task(task_id="t2", task_type="shell", payload={"command": "exit 1"})
    await executor.submit(task)
    for _ in range(20):
        await asyncio.sleep(0.1)
        result = executor.get_result("t2")
        if result and result.status not in (TaskStatus.PENDING, TaskStatus.RUNNING):
            break
    assert result.status == TaskStatus.FAILED
    assert result.exit_code == 1


@pytest.mark.asyncio
async def test_execute_shell_blocked_command(executor):
    task = Task(task_id="t3", task_type="shell", payload={"command": "rm -rf / --no-preserve-root"})
    await executor.submit(task)
    for _ in range(20):
        await asyncio.sleep(0.1)
        result = executor.get_result("t3")
        if result and result.status not in (TaskStatus.PENDING, TaskStatus.RUNNING):
            break
    assert result.status == TaskStatus.FAILED
    assert "blocked" in result.error.lower()


@pytest.mark.asyncio
async def test_execute_shell_no_command(executor):
    task = Task(task_id="t4", task_type="shell", payload={})
    await executor.submit(task)
    for _ in range(20):
        await asyncio.sleep(0.1)
        result = executor.get_result("t4")
        if result and result.status not in (TaskStatus.PENDING, TaskStatus.RUNNING):
            break
    assert result.status == TaskStatus.FAILED
    assert "command" in result.error.lower()


@pytest.mark.asyncio
async def test_execute_python(executor):
    task = Task(task_id="t5", task_type="python", payload={"code": "print('py-ok')"})
    await executor.submit(task)
    for _ in range(20):
        await asyncio.sleep(0.1)
        result = executor.get_result("t5")
        if result and result.status not in (TaskStatus.PENDING, TaskStatus.RUNNING):
            break
    assert result.status == TaskStatus.COMPLETED
    assert "py-ok" in result.stdout


@pytest.mark.asyncio
async def test_execute_unknown_task_type(executor):
    task = Task(task_id="t6", task_type="unknown_xyz", payload={})
    await executor.submit(task)
    for _ in range(20):
        await asyncio.sleep(0.1)
        result = executor.get_result("t6")
        if result and result.status not in (TaskStatus.PENDING, TaskStatus.RUNNING):
            break
    assert result.status == TaskStatus.FAILED
    assert "Unknown task type" in result.error


@pytest.mark.asyncio
async def test_task_result_duration(executor):
    task = Task(task_id="t7", task_type="shell", payload={"command": "true"})
    await executor.submit(task)
    for _ in range(20):
        await asyncio.sleep(0.1)
        result = executor.get_result("t7")
        if result and result.status not in (TaskStatus.PENDING, TaskStatus.RUNNING):
            break
    assert result.duration is not None
    assert result.duration >= 0


def test_is_blocked_command(executor):
    assert executor._is_blocked_command("rm -rf /") is True
    assert executor._is_blocked_command("echo hello") is False
    assert executor._is_blocked_command("mkfs.ext4 /dev/sda") is True
    assert executor._is_blocked_command("ls -la") is False


def test_task_from_dict():
    data = {"task_id": "abc", "type": "shell", "payload": {"command": "ls"}}
    task = Task.from_dict(data)
    assert task.task_id == "abc"
    assert task.task_type == "shell"
    assert task.payload["command"] == "ls"


def test_get_running_tasks_empty(executor):
    assert executor.get_running_tasks() == []


def test_get_result_missing(executor):
    assert executor.get_result("nonexistent") is None
