# tests/agent/test_executor.py

"""Unit tests for Executor."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.executor import CommandResult, CommandTimeoutError, Executor


@pytest.fixture
def executor(tmp_path):
    """Create Executor instance."""
    return Executor(
        repo_path=tmp_path,
        policy=MagicMock(),
        project=MagicMock(),
        journal=MagicMock(),
        interactor=MagicMock(),
    )


@pytest.mark.asyncio
async def test_run_success(executor):
    """Test successful command execution."""
    # Mock asyncio.create_subprocess_shell
    mock_proc = AsyncMock()
    mock_proc.returncode = 0
    mock_proc.stdout.readline = AsyncMock(side_effect=[b"output\n", b""])
    mock_proc.stderr.readline = AsyncMock(side_effect=[b""])
    mock_proc.wait.return_value = None

    with patch("asyncio.create_subprocess_shell", return_value=mock_proc) as mock_shell:
        executor.cmd_policy.check = MagicMock(return_value=(True, None))

        result = await executor.run("echo test")

        assert result.returncode == 0
        assert "output" in result.stdout
        mock_shell.assert_called_once()


@pytest.mark.asyncio
async def test_run_policy_blocked(executor):
    """Test command blocked by policy."""
    executor.cmd_policy.check = MagicMock(return_value=(False, "Blocked"))

    result = await executor.run("rm -rf /")

    assert result.returncode == 125
    assert "Blocked" in result.stderr


@pytest.mark.asyncio
async def test_run_timeout(executor):
    """Test command timeout."""
    # Mock process that never finishes
    mock_proc = AsyncMock()
    mock_proc.returncode = None
    # Simulate wait() being cancelled by timeout
    mock_proc.wait.side_effect = asyncio.CancelledError()
    mock_proc.stdout.readline = AsyncMock(return_value=b"")
    mock_proc.stderr.readline = AsyncMock(return_value=b"")
    mock_proc.kill = MagicMock()

    # We need to mock wait_for to raise TimeoutError,
    # BUT Executor uses asyncio.wait() inside run() for reading streams,
    # and asyncio.wait_for() is usually called by the *caller* of executor.run().
    # However, executor.run() handles CancelledError internally to kill the process.

    with patch("asyncio.create_subprocess_shell", return_value=mock_proc):
        executor.cmd_policy.check = MagicMock(return_value=(True, None))

        # Simulate external timeout cancelling the task
        task = asyncio.create_task(executor.run("sleep 10"))
        await asyncio.sleep(0.1)
        task.cancel()

        with pytest.raises(CommandTimeoutError):
            await task

        mock_proc.kill.assert_called()


@pytest.mark.asyncio
async def test_run_tests(executor):
    """Test run_tests wrapper."""
    executor.project.commands = {"test": "pytest"}
    executor.run = AsyncMock(return_value=CommandResult("pytest", 0, "ok", ""))

    result = await executor.run_tests()

    assert result.returncode == 0
    executor.run.assert_called_with("pytest")


@pytest.mark.asyncio
async def test_run_install_skipped(executor):
    """Test run_install when no command configured."""
    executor.project.commands = {}

    result = await executor.run_install()

    assert "skipped" in result.command
    assert result.returncode == 0
