# tests/agent/test_tooled.py

"""Unit tests for ToolHandler."""
# pylint: disable=protected-access

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.executor import CommandTimeoutError
from agent.tooled import RestartSession, ToolHandler
from llm.client import LLMResponse


@pytest.fixture
def tool_handler(tmp_path):
    """Create a ToolHandler instance with mocks."""
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    project = MagicMock()
    project.main_branch = "main"
    project.protected_files = []
    executor = MagicMock()
    journal = MagicMock()
    progress = MagicMock()
    llm = MagicMock()
    context_gatherer = MagicMock()
    tasks_manager = MagicMock()
    git = MagicMock()

    return ToolHandler(
        repo_path=repo_path,
        project=project,
        executor=executor,
        journal=journal,
        progress=progress,
        llm=llm,
        context_gatherer=context_gatherer,
        tasks_manager=tasks_manager,
        git=git,
    )


@pytest.mark.asyncio
async def test_write_file(tool_handler):
    """Test writing a file successfully."""
    file_path = "test.txt"
    content = "Hello World"

    result = await tool_handler._write_file(file_path, content)

    assert "Successfully wrote" in result
    assert (tool_handler.repo_path / file_path).read_text(encoding="utf-8") == content
    tool_handler.progress.add_action.assert_called_with("WRITE", file_path, "SUCCESS")


@pytest.mark.asyncio
async def test_write_file_protected(tool_handler):
    """Test writing to a protected file fails."""
    tool_handler.project.protected_files = ["protected.txt"]
    file_path = "protected.txt"

    result = await tool_handler._write_file(file_path, "content")

    assert "Access denied" in result
    assert "protected" in result


@pytest.mark.asyncio
async def test_write_file_outside_repo(tool_handler):
    """Test writing outside the repo fails."""
    file_path = "../outside.txt"

    result = await tool_handler._write_file(file_path, "content")

    assert "Access denied" in result
    assert "outside repository" in result


@pytest.mark.asyncio
async def test_write_file_is_dir(tool_handler):
    """Test writing to a path that is a directory fails."""
    (tool_handler.repo_path / "dir").mkdir()

    result = await tool_handler._write_file("dir", "content")
    assert "is a directory" in result


@pytest.mark.asyncio
async def test_dynamic_tool_registration(tool_handler):
    """Test registering a new tool dynamically."""
    mock_tool = AsyncMock(return_value="Dynamic Result")
    tool_def = {"name": "dynamic_tool", "description": "test"}

    tool_handler.register("dynamic_tool", tool_def, mock_tool)

    assert "dynamic_tool" in tool_handler.tool_definitions
    assert "dynamic_tool" in tool_handler.tool_implementations
    assert tool_handler.tool_implementations["dynamic_tool"] == mock_tool


@pytest.mark.asyncio
async def test_read_file(tool_handler):
    """Test reading a file successfully."""
    file_path = "read_test.txt"
    content = "Read Me"
    (tool_handler.repo_path / file_path).write_text(content, encoding="utf-8")

    result = await tool_handler._read_file(file_path)
    assert result == content
    tool_handler.progress.add_action.assert_called_with("READ", file_path, "SUCCESS")


@pytest.mark.asyncio
async def test_read_file_errors(tool_handler):
    """Test read file error conditions."""
    # Missing path

    assert "Missing path" in await tool_handler._read_file("")

    # Outside repo
    assert "Access denied" in await tool_handler._read_file("../outside.txt")

    # Protected
    tool_handler.project.protected_files = ["secret.txt"]
    assert "protected" in await tool_handler._read_file("secret.txt")

    # Not found
    assert "not found" in await tool_handler._read_file("nonexistent.txt")

    # Is directory
    (tool_handler.repo_path / "dir").mkdir(exist_ok=True)
    assert "is a directory" in await tool_handler._read_file("dir")


@pytest.mark.asyncio
async def test_run_shell(tool_handler):
    """Test shell command execution."""
    tool_handler.executor.run = AsyncMock()
    mock_res = MagicMock()
    mock_res.returncode = 0
    mock_res.stdout = "output"
    mock_res.stderr = ""
    tool_handler.executor.run.return_value = mock_res

    result = await tool_handler._run_shell("echo hello")

    assert "Exit Code: 0" in result
    assert "STDOUT:\noutput" in result
    tool_handler.executor.run.assert_called_once()
    args, kwargs = tool_handler.executor.run.call_args
    assert args[0] == "echo hello"
    assert kwargs["gate"] == "shell"


@pytest.mark.asyncio
async def test_run_shell_install_gate(tool_handler):
    """Test shell command with install gate heuristic."""
    tool_handler.executor.run = AsyncMock()
    mock_res = MagicMock()
    mock_res.returncode = 0
    mock_res.stdout = ""
    mock_res.stderr = ""
    tool_handler.executor.run.return_value = mock_res

    await tool_handler._run_shell("npm install")

    _, kwargs = tool_handler.executor.run.call_args
    assert kwargs["gate"] == "add-package"


@pytest.mark.asyncio
async def test_run_shell_interaction(tool_handler):
    """Test shell command execution with interaction callback."""
    tool_handler.executor.run = AsyncMock()
    tool_handler.llm.interact_with_shell = AsyncMock()
    tool_handler.llm.interact_with_shell.return_value.content = "user input"

    # Mock executor.run to execute the callback passed to it
    async def mock_run_side_effect(_command, _gate=None, interaction_callback=None, **_kwargs):
        if interaction_callback:
            await interaction_callback("cmd", "stdout", "stderr")
        return MagicMock(returncode=0, stdout="", stderr="")

    tool_handler.executor.run.side_effect = mock_run_side_effect

    await tool_handler._run_shell("interactive_cmd", cmd_instruction="instruction")

    tool_handler.llm.interact_with_shell.assert_called_once()
    assert tool_handler.llm.interact_with_shell.call_args[1]["instruction"] == "instruction"


@pytest.mark.asyncio
async def test_run_shell_timeout(tool_handler):
    """Test shell command timeout."""
    mock_result = MagicMock(returncode=124, stdout="", stderr="Timeout")
    tool_handler.executor.run = AsyncMock(side_effect=CommandTimeoutError(mock_result))

    result = await tool_handler._run_shell("sleep 10")

    assert "Exit Code: 124" in result
    assert "STDERR:\nTimeout" in result


@pytest.mark.asyncio
async def test_find_package(tool_handler):
    """Test find_package tool."""
    tool_handler.executor.run = AsyncMock()
    mock_res = MagicMock()
    mock_res.returncode = 0
    mock_res.stdout = "1.0.0\n1.0.1"
    mock_res.stderr = ""
    tool_handler.executor.run.return_value = mock_res

    result = await tool_handler._find_package("pkg", "python")

    assert "1.0.0" in result
    tool_handler.executor.run.assert_called_once()
    assert "pip index versions pkg" in tool_handler.executor.run.call_args[0][0]

    # Node
    tool_handler.executor.run.reset_mock()
    await tool_handler._find_package("pkg", "node")
    assert "npm view pkg versions" in tool_handler.executor.run.call_args[0][0]

    # Error cases
    assert "Missing" in await tool_handler._find_package("", "python")
    assert "Unsupported" in await tool_handler._find_package("pkg", "rust")


@pytest.mark.asyncio
async def test_run_loop(tool_handler):
    """Test the tool execution loop."""
    session = MagicMock()
    session.send = AsyncMock()
    session.add_tool_result = MagicMock()

    # Initial response has a tool call
    initial_response = MagicMock(spec=LLMResponse)
    initial_response.tool_calls = [
        {"id": "call_1", "function": {"name": "run_shell", "arguments": '{"command": "echo test"}'}}
    ]
    initial_response.content = "Thinking..."

    # Mock tool implementation
    tool_handler.tool_implementations["run_shell"] = AsyncMock(return_value="Shell Output")

    # Second response has no tool calls (ends loop)
    second_response = MagicMock(spec=LLMResponse)
    second_response.tool_calls = []
    second_response.content = "Done"
    session.send.return_value = second_response

    final_response = await tool_handler.run_loop(session, initial_response, "instruction")

    assert final_response == second_response
    tool_handler.tool_implementations["run_shell"].assert_called_with(
        command="echo test", cmd_instruction="instruction", session=session
    )
    session.add_tool_result.assert_called_with("call_1", "Shell Output")
    session.send.assert_called_once()


@pytest.mark.asyncio
async def test_run_loop_invalid_tool(tool_handler):
    """Test run loop with unknown tool."""
    session = MagicMock()
    session.send = AsyncMock()
    session.add_tool_result = MagicMock()

    initial_response = MagicMock(spec=LLMResponse)
    initial_response.tool_calls = [{"id": "call_1", "function": {"name": "unknown_tool", "arguments": "{}"}}]

    second_response = MagicMock(spec=LLMResponse)
    second_response.tool_calls = []
    session.send.return_value = second_response

    await tool_handler.run_loop(session, initial_response, "")

    session.add_tool_result.assert_called_with("call_1", "Error: Unknown tool 'unknown_tool'")


@pytest.mark.asyncio
async def test_run_loop_json_error(tool_handler):
    """Test run loop with invalid JSON arguments."""
    session = MagicMock()
    session.send = AsyncMock()
    session.add_tool_result = MagicMock()

    initial_response = MagicMock(spec=LLMResponse)
    initial_response.tool_calls = [{"id": "call_1", "function": {"name": "run_shell", "arguments": "{invalid_json"}}]

    # Should continue to next tool or finish if loop continues, but here it just logs error and continues loop
    # We need session.send to return something to break loop
    second_response = MagicMock(spec=LLMResponse)
    second_response.tool_calls = []
    session.send.return_value = second_response

    await tool_handler.run_loop(session, initial_response, "")

    args, _ = session.add_tool_result.call_args
    assert "Error: Invalid JSON" in args[1]


@pytest.mark.asyncio
async def test_run_loop_max_cycles(tool_handler):
    """Test that the tool loop exits after max_cycles."""
    session = MagicMock()
    session.send = AsyncMock()
    session.add_tool_result = MagicMock()

    # Mock a response that always has a tool call
    looping_response = MagicMock(spec=LLMResponse)
    looping_response.tool_calls = [
        {"id": "call_1", "function": {"name": "run_shell", "arguments": '{"command": "loop"}'}}
    ]
    session.send.return_value = looping_response

    # Mock the tool implementation
    tool_handler.tool_implementations["run_shell"] = AsyncMock(return_value="Looping")

    final_response = await tool_handler.run_loop(session, looping_response, "")

    # Should be the last response from the LLM after hitting the limit
    assert final_response == looping_response
    # Default max_cycles is 15
    assert session.send.call_count == 15


@pytest.mark.asyncio
async def test_run_loop_tool_exception(tool_handler):
    """Test that the loop handles exceptions within tool implementations."""
    session = MagicMock()
    session.send = AsyncMock(return_value=MagicMock(tool_calls=[]))  # Stop after one loop
    session.add_tool_result = MagicMock()

    initial_response = MagicMock(spec=LLMResponse)
    initial_response.tool_calls = [{"id": "call_1", "function": {"name": "failing_tool", "arguments": "{}"}}]

    # Register a tool that will raise an exception
    failing_impl = AsyncMock(side_effect=ValueError("Tool failed!"))
    tool_handler.register("failing_tool", {}, failing_impl)

    await tool_handler.run_loop(session, initial_response, "")

    session.add_tool_result.assert_called_with("call_1", "Error executing tool: Tool failed!")


@pytest.mark.asyncio
async def test_summarize_and_restart(tool_handler):
    """Test summarize_and_restart tool raises exception."""
    with pytest.raises(RestartSession) as exc:
        await tool_handler._summarize_and_restart("Summary text")
    assert exc.value.summary == "Summary text"


@pytest.mark.asyncio
async def test_run_loop_restart_session(tool_handler):
    """Test run_loop handles RestartSession."""
    session = MagicMock()
    session.send = AsyncMock()
    session.restart_with_summary = MagicMock()
    session.add_tool_result = MagicMock()

    # Initial response calls summarize_and_restart
    initial_response = MagicMock(spec=LLMResponse)
    initial_response.tool_calls = [
        {"id": "call_1", "function": {"name": "summarize_and_restart", "arguments": '{"summary": "restart"}'}}
    ]

    # Mock implementation to raise RestartSession (as it does in real code)
    tool_handler.tool_implementations["summarize_and_restart"] = tool_handler._summarize_and_restart

    # Mock session.send to return a response without tool calls the second time to exit run_loop
    final_response = MagicMock(spec=LLMResponse)
    final_response.tool_calls = []
    session.send.side_effect = [final_response]

    await tool_handler.run_loop(session, initial_response, "")

    session.restart_with_summary.assert_called_with("restart")


@pytest.mark.asyncio
async def test_pick_task(tool_handler):
    """Test pick_task tool."""
    mock_task = MagicMock()
    mock_task.id = "001"
    mock_task.title = "Test Task"
    mock_task.priority = "P0"
    tool_handler.tasks_manager.get_next_task.return_value = mock_task
    tool_handler.tasks_manager.recover_active_task.return_value = None
    tool_handler.tasks_manager.claim_task.return_value = (True, "Claimed")

    # Mock executor.run for git status check
    mock_status = MagicMock()
    mock_status.returncode = 0
    mock_status.stdout = ""
    tool_handler.executor.run = AsyncMock(return_value=mock_status)

    result = await tool_handler._pick_task()
    assert "SUCCESS: PICKED task 001" in result
    assert "Title: Test Task" in result
    tool_handler.tasks_manager.claim_task.assert_called_with("001", tool_handler.git)

    # Verify sync with main branch occurred (since recover_active_task returned None)
    tool_handler.git.checkout.assert_called_with("main")
    tool_handler.git.pull.assert_called_with("main")
    tool_handler.tasks_manager.reload.assert_called()


@pytest.mark.asyncio
async def test_pick_task_recovery(tool_handler):
    """Test pick_task tool when recovering an active task (skips sync)."""
    mock_task = MagicMock()
    mock_task.id = "001"
    mock_task.title = "Recovered Task"
    mock_task.priority = "P0"
    tool_handler.tasks_manager.recover_active_task.return_value = mock_task
    tool_handler.tasks_manager.claim_task.return_value = (True, "Recovered")

    # Mock executor.run for git status check
    mock_status = MagicMock()
    mock_status.returncode = 0
    mock_status.stdout = ""
    tool_handler.executor.run = AsyncMock(return_value=mock_status)

    result = await tool_handler._pick_task()
    assert "SUCCESS: RECOVERED task 001" in result
    tool_handler.tasks_manager.claim_task.assert_called_with("001", tool_handler.git)

    # Verify sync with main branch did NOT occur
    tool_handler.git.pull.assert_not_called()
    tool_handler.tasks_manager.reload.assert_not_called()


@pytest.mark.asyncio
async def test_pick_task_dirty_repo_on_main(tool_handler):
    """Test pick_task stashes changes when on main branch."""
    # Setup mocks
    tool_handler.tasks_manager.get_next_task.return_value = MagicMock()
    tool_handler.tasks_manager.recover_active_task.return_value = None
    tool_handler.tasks_manager.claim_task.return_value = (True, "Claimed")
    tool_handler.git.current_branch.return_value = "main"

    # Mock executor.run to show a dirty status, then a clean one after stash
    dirty_status = MagicMock(returncode=0, stdout=" M file.txt")
    clean_status = MagicMock(returncode=0, stdout="")
    tool_handler.executor.run = AsyncMock(side_effect=[dirty_status, clean_status])

    await tool_handler._pick_task()

    # Assert that 'git stash' was called
    tool_handler.executor.run.assert_any_call("git stash -u")
    tool_handler.journal.print.assert_any_call("🧹 Stashing changes on main to allow pull...")


@pytest.mark.asyncio
async def test_pick_task_dirty_repo_on_feature_branch(tool_handler):
    """Test pick_task saves WIP when on a feature branch."""
    # Setup mocks
    tool_handler.tasks_manager.recover_active_task.return_value = None
    tool_handler.git.current_branch.return_value = "feature/abc"
    tool_handler.executor.run = AsyncMock(return_value=MagicMock(returncode=0, stdout=" M file.txt"))

    with patch.object(tool_handler, "_save_wip", new_callable=AsyncMock) as mock_save_wip:
        await tool_handler._pick_task()
        mock_save_wip.assert_called_once_with("feature/abc", "WIP: Crash recovery")


@pytest.mark.asyncio
async def test_complete_task(tool_handler):
    """Test complete_task tool."""
    tool_handler.tasks_manager.complete_task.return_value = (True, "Task 001 marked as Done.")

    result = await tool_handler._complete_task("001")
    assert "SUCCESS" in result
    assert "marked as Done" in result
    tool_handler.tasks_manager.complete_task.assert_called_with("001")


@pytest.mark.asyncio
async def test_git_checkout(tool_handler):
    """Test git_checkout tool."""

    result = await tool_handler._git_checkout("feature-branch")
    assert "Checked out branch feature-branch" in result
    tool_handler.git.checkout_branch.assert_called_with("feature-branch")


@pytest.mark.asyncio
async def test_git_commit(tool_handler):
    """Test git_commit tool."""

    result = await tool_handler._git_commit("Initial commit")
    assert "Committed with message: Initial commit" in result
    tool_handler.git.add_all.assert_called_once()
    tool_handler.git.commit.assert_called_with("Initial commit")


@pytest.mark.asyncio
async def test_git_push(tool_handler):
    """Test git_push tool."""
    # Case 1: Explicit branch

    result = await tool_handler._git_push("feature-branch")
    assert "Pushed branch feature-branch" in result
    tool_handler.git.push.assert_called_with("feature-branch")

    # Case 2: Current branch
    tool_handler.git.current_branch.return_value = "main"
    result = await tool_handler._git_push()
    assert "Pushed branch main" in result
    tool_handler.git.push.assert_called_with("main")


@pytest.mark.asyncio
async def test_git_merge(tool_handler):
    """Test git_merge tool."""

    result = await tool_handler._git_merge("feature", "main")
    assert "Merged feature into main" in result

    tool_handler.git.checkout.assert_called_with("main")
    tool_handler.git.pull.assert_called_with("main")
    tool_handler.git.run.assert_called_with("merge", "feature")

    # Error case
    assert "Error: Missing" in await tool_handler._git_merge("", "main")


@pytest.mark.asyncio
async def test_run_tests(tool_handler):
    """Test run_tests tool."""
    mock_res = MagicMock()
    mock_res.returncode = 0
    mock_res.stdout = "tests passed"
    mock_res.stderr = ""
    tool_handler.executor.run_tests = AsyncMock(return_value=mock_res)

    result = await tool_handler._run_tests()
    assert "Exit Code: 0" in result
    assert "tests passed" in result
    tool_handler.executor.run_tests.assert_called_once()


@pytest.mark.asyncio
async def test_check_run_limit(tool_handler):
    """Test check_run_limit tool."""
    tool_handler.llm.check_run_limit.return_value = (True, "WITHIN_LIMIT")

    result = await tool_handler._check_run_limit()
    assert "WITHIN_LIMIT" in result

    tool_handler.llm.check_run_limit.return_value = (False, "DAILY_LIMIT_EXCEEDED")
    result = await tool_handler._check_run_limit()
    assert "DAILY_LIMIT_EXCEEDED" in result


@pytest.mark.asyncio
async def test_agent_sleep(tool_handler):
    """Test agent_sleep tool."""
    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        result = await tool_handler._agent_sleep(5)
        assert "Slept for 5 seconds" in result
        mock_sleep.assert_called_with(5)


@pytest.mark.asyncio
async def test_agent_exit(tool_handler):
    """Test agent_exit tool."""
    with patch("sys.exit") as mock_exit:
        await tool_handler._agent_exit(rc=1)
        mock_exit.assert_called_with(1)
