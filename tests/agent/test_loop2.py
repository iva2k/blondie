# tests/agent/test_loop2.py

"""Unit tests for BlondieOrchestrator (v2 loop)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.loop2 import BlondieOrchestrator


@pytest.fixture
def mock_deps(tmp_path):
    """Mock all dependencies for BlondieOrchestrator."""
    # Create dummy files to satisfy __init__ paths
    agent_dir = tmp_path / ".agent"
    agent_dir.mkdir()
    (agent_dir / "project.yaml").write_text("id: test\npolicy: POLICY.yaml", encoding="utf-8")
    (agent_dir / "POLICY.yaml").write_text("autonomy: {}", encoding="utf-8")
    (agent_dir / "TASKS.md").write_text("# Tasks", encoding="utf-8")
    (agent_dir / "secrets.env.yaml").write_text("llm: {}", encoding="utf-8")
    (agent_dir / "llm_config.yaml").write_text("providers: {}", encoding="utf-8")
    (agent_dir / "progress.txt").write_text("", encoding="utf-8")

    with (
        patch("agent.loop2.Project") as mock_project,
        patch("agent.loop2.Journal") as mock_journal,
        patch("agent.loop2.Policy") as mock_policy,
        patch("agent.loop2.TasksManager") as mock_tasks_manager,
        patch("agent.loop2.GitCLI") as mock_git_cli,
        patch("agent.loop2.ConsoleInteractionProvider"),
        patch("agent.loop2.Executor") as mock_executor,
        patch("agent.loop2.GitIgnore"),
        patch("agent.loop2.ProgressManager") as mock_progress,
        patch("agent.loop2.ContextGatherer") as mock_context,
        patch("agent.loop2.LLMRouter") as mock_router,
        patch("agent.loop2.ToolHandler") as mock_tool_handler,
    ):
        mock_project.from_file.return_value.id = "test"
        mock_project.from_file.return_value.policy = "POLICY.yaml"
        mock_router.return_value.daily_cost = 0.0
        mock_router.return_value.close = AsyncMock()

        yield {
            "project": mock_project,
            "journal": mock_journal,
            "policy": mock_policy,
            "tasks_manager": mock_tasks_manager,
            "git_cli": mock_git_cli,
            "executor": mock_executor,
            "progress": mock_progress,
            "context": mock_context,
            "router": mock_router,
            "tool_handler": mock_tool_handler,
            "repo_path": tmp_path,
        }


def test_init(mock_deps):
    """Test initialization and component wiring."""
    orch = BlondieOrchestrator(str(mock_deps["repo_path"]))
    assert orch.repo_path == mock_deps["repo_path"]
    mock_deps["router"].assert_called()
    mock_deps["tool_handler"].assert_called()
    # Verify register_skills was called to wire up recursion
    mock_deps["router"].return_value.register_skills.assert_called_with(
        mock_deps["tool_handler"].return_value, mock_deps["context"].return_value
    )


@pytest.mark.asyncio
async def test_run(mock_deps):
    """Test the main execution loop."""
    orch = BlondieOrchestrator(str(mock_deps["repo_path"]))

    # Mock session and response
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_deps["router"].return_value.start_chat.return_value = mock_session
    mock_session.send = AsyncMock(return_value=mock_response)
    mock_deps["tool_handler"].return_value.run_loop = AsyncMock()

    await orch.run()

    mock_deps["router"].return_value.start_chat.assert_called_with("coding_orchestrator", orch.context_gatherer)
    mock_session.send.assert_called()
    mock_deps["tool_handler"].return_value.run_loop.assert_called_with(mock_session, mock_response, "Orchestrator")
    mock_deps["router"].return_value.close.assert_called()


@pytest.mark.asyncio
async def test_run_exception(mock_deps):
    """Test exception handling in run loop."""
    orch = BlondieOrchestrator(str(mock_deps["repo_path"]))
    mock_deps["router"].return_value.start_chat.side_effect = Exception("Boom")

    await orch.run()

    # Should log crash and close
    found_crash_log = False
    for call in mock_deps["journal"].return_value.print.call_args_list:
        if call.args and "💥 Orchestrator crashed: Boom" in str(call.args[0]):
            found_crash_log = True
            break
    assert found_crash_log, "Crash log not found in journal.print calls"
    mock_deps["router"].return_value.close.assert_called()
