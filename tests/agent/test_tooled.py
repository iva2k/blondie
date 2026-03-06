# tests/agent/test_tooled.py

"""Unit tests for ToolHandler."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from agent.executor import CommandTimeoutError
from agent.tooled import ToolHandler
from llm.client import LLMResponse


@pytest.fixture
def tool_handler(tmp_path):
    """Create a ToolHandler instance with mocks."""
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    project = MagicMock()
    project.protected_files = []
    executor = MagicMock()
    journal = MagicMock()
    progress = MagicMock()
    llm = MagicMock()
    context_gatherer = MagicMock()

    return ToolHandler(
        repo_path=repo_path,
        project=project,
        executor=executor,
        journal=journal,
        progress=progress,
        llm=llm,
        context_gatherer=context_gatherer,
    )


@pytest.mark.asyncio
async def test_write_file(tool_handler):
    """Test writing a file successfully."""
    file_path = "test.txt"
    content = "Hello World"

    # pylint: disable=protected-access
    result = await tool_handler._write_file(file_path, content)

    assert "Successfully wrote" in result
    assert (tool_handler.repo_path / file_path).read_text(encoding="utf-8") == content
    tool_handler.progress.add_action.assert_called_with("WRITE", file_path, "SUCCESS")


@pytest.mark.asyncio
async def test_write_file_protected(tool_handler):
    """Test writing to a protected file fails."""
    tool_handler.project.protected_files = ["protected.txt"]
    file_path = "protected.txt"

    # pylint: disable=protected-access
    result = await tool_handler._write_file(file_path, "content")

    assert "Access denied" in result
    assert "protected" in result


@pytest.mark.asyncio
async def test_write_file_outside_repo(tool_handler):
    """Test writing outside the repo fails."""
    file_path = "../outside.txt"

    # pylint: disable=protected-access
    result = await tool_handler._write_file(file_path, "content")

    assert "Access denied" in result
    assert "outside repository" in result


@pytest.mark.asyncio
async def test_write_file_is_dir(tool_handler):
    """Test writing to a path that is a directory fails."""
    (tool_handler.repo_path / "dir").mkdir()
    # pylint: disable=protected-access
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

    # pylint: disable=protected-access
    result = await tool_handler._read_file(file_path)
    assert result == content
    tool_handler.progress.add_action.assert_called_with("READ", file_path, "SUCCESS")


@pytest.mark.asyncio
async def test_read_file_errors(tool_handler):
    """Test read file error conditions."""
    # Missing path
    # pylint: disable=protected-access
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

    # pylint: disable=protected-access
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

    # pylint: disable=protected-access
    await tool_handler._run_shell("npm install")

    _, kwargs = tool_handler.executor.run.call_args
    assert kwargs["gate"] == "add-package"


@pytest.mark.asyncio
async def test_run_shell_timeout(tool_handler):
    """Test shell command timeout."""
    mock_result = MagicMock(returncode=124, stdout="", stderr="Timeout")
    tool_handler.executor.run = AsyncMock(side_effect=CommandTimeoutError(mock_result))

    # pylint: disable=protected-access
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

    # pylint: disable=protected-access
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
        command="echo test", cmd_instruction="instruction"
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
