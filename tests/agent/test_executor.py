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


@pytest.mark.asyncio
async def test_run_interactive_logic(executor):
    """Test the interaction loop inside run()."""
    mock_proc = AsyncMock()
    mock_proc.returncode = None
    mock_proc.stdin = AsyncMock()
    mock_proc.stdin.write = MagicMock()
    mock_proc.stdin.drain = AsyncMock()

    # Simulate stdout arriving in chunks
    # 1. "Enter name: "
    # 2. EOF
    mock_proc.stdout.readline = AsyncMock(side_effect=[b"Enter name: ", b""])
    mock_proc.stderr.readline = AsyncMock(return_value=b"")

    # Simulate process finishing after interaction
    async def delayed_exit():
        await asyncio.sleep(0.2)  # Wait for interaction
        mock_proc.returncode = 0

    mock_proc.wait.side_effect = delayed_exit

    # Interaction callback that responds to prompt
    async def interaction_callback(_cmd, stdout, _stderr):
        await asyncio.sleep(0)
        if "Enter name:" in stdout:
            return "Blondie"
        return ""

    with patch("asyncio.create_subprocess_shell", return_value=mock_proc):
        executor.cmd_policy.check = MagicMock(return_value=(True, None))

        # Mock asyncio.wait to simulate timeout and trigger interaction
        async def mock_wait(fs, **_kwargs):
            await asyncio.sleep(0)
            done = {f for f in fs if f.done()}
            if done:
                return done, set(fs) - done
            # Simulate timeout to trigger interaction
            await asyncio.sleep(0.1)
            done = {f for f in fs if f.done()}
            if done:
                return done, set(fs) - done
            return set(), set(fs)

        with patch("agent.executor.asyncio.wait", side_effect=mock_wait):
            result = await executor.run(
                "interactive_script",
                interaction_callback=interaction_callback,
            )

    assert result.returncode == 0
    assert "Enter name:" in result.stdout
    # Verify input was written to stdin
    mock_proc.stdin.write.assert_called_with(b"Blondie\n")
    mock_proc.stdin.drain.assert_called()


@pytest.mark.asyncio
async def test_run_list_command(executor):
    """Test running command as a list."""
    mock_proc = AsyncMock()
    mock_proc.returncode = 0
    mock_proc.stdout.readline = AsyncMock(side_effect=[b"", b""])
    mock_proc.stderr.readline = AsyncMock(side_effect=[b"", b""])
    mock_proc.wait.return_value = None

    with patch("asyncio.create_subprocess_shell", return_value=mock_proc) as mock_shell:
        executor.cmd_policy.check = MagicMock(return_value=(True, None))

        await executor.run(["echo", "hello"])

        # Verify it was joined correctly
        args = mock_shell.call_args[0]
        # Basic check that it's a string now
        assert isinstance(args[0], str)
        assert "echo" in args[0]
        assert "hello" in args[0]


@pytest.mark.asyncio
async def test_run_interactive_abort(executor):
    """Test aborting interaction with ^C."""
    mock_proc = AsyncMock()
    mock_proc.returncode = None
    mock_proc.stdin = AsyncMock()
    mock_proc.kill = MagicMock()

    # Simulate stdout to trigger interaction
    mock_proc.stdout.readline = AsyncMock(side_effect=[b"Prompt: ", b""])
    mock_proc.stderr.readline = AsyncMock(return_value=b"")

    # Callback returns abort signal
    async def interaction_callback(*_args):
        await asyncio.sleep(0)
        return "^C"

    # Mock wait to trigger interaction logic then exit
    async def mock_wait(fs, **_kwargs):
        await asyncio.sleep(0)
        return set(), set(fs)  # Simulate timeout to trigger check

    # We also need process.wait() to eventually return to exit the loop
    async def delayed_exit():
        await asyncio.sleep(0.1)
        mock_proc.returncode = -1

    mock_proc.wait.side_effect = delayed_exit

    with patch("asyncio.create_subprocess_shell", return_value=mock_proc):
        executor.cmd_policy.check = MagicMock(return_value=(True, None))
        with patch("agent.executor.asyncio.wait", side_effect=mock_wait):
            await executor.run("cmd", interaction_callback=interaction_callback)

    mock_proc.kill.assert_called()


@pytest.mark.asyncio
async def test_run_build(executor):
    """Test run_build wrapper."""
    executor.project.commands = {"build": "make"}
    executor.run = AsyncMock(return_value=CommandResult("make", 0, "ok", ""))

    result = await executor.run_build()

    assert result.returncode == 0
    executor.run.assert_called_with("make")
