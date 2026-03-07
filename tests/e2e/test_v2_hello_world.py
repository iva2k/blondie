# tests/e2e/test_v2_hello_world.py

"""End-to-end test for v2 orchestrator loop."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.loop2 import BlondieOrchestrator
from agent.tasks import TasksManager, TaskStatus
from lib.setup_repo import setup_repo
from llm.client import LLMResponse


@pytest.fixture
def temp_repo(tmp_path: Path) -> Path:
    """Create a temporary repository with agent configuration."""
    repo_dir = tmp_path / "repo-e2e"
    remote_dir = tmp_path / "remote-e2e.git"
    root_dir = Path(__file__).parents[2]
    setup_repo(repo_dir, remote_dir, root_dir=root_dir)

    agent_dir = repo_dir / ".agent"

    # 1. project.yaml
    (agent_dir / "project.yaml").write_text(
        """
id: test-project
policy: POLICY.yaml
git_user: TestBot
git_email: bot@test.com
""",
        encoding="utf-8",
    )

    # 2. POLICY.yaml
    (agent_dir / "POLICY.yaml").write_text(
        """
autonomy:
  gates:
    run_shell: allow
    write_file: allow
""",
        encoding="utf-8",
    )

    # 3. TASKS.md
    (agent_dir / "TASKS.md").write_text(
        """
# Tasks
Status: id | priority | title
- [ ] 001 | P0 | Create hello.txt with content 'Hello World' |
""",
        encoding="utf-8",
    )

    # 5. llm_config.yaml (dummy)
    (agent_dir / "llm_config.yaml").write_text("providers: {}", encoding="utf-8")

    # 6. progress.txt
    (agent_dir / "progress.txt").write_text("", encoding="utf-8")

    return repo_dir


@pytest.mark.asyncio
async def test_v2_hello_world_task(temp_repo: Path):
    """
    Verify that the v2 orchestrator can pick up a task, execute tools, and complete it.
    We mock the LLM responses to simulate the decision making.
    """
    # Mock the LLMRouter's start_chat to return our controlled session
    with (
        patch("agent.router.LLMRouter.start_chat") as mock_start_chat,
        patch("agent.router.LLMRouter.close", new_callable=AsyncMock),
    ):
        mock_session = MagicMock()
        mock_start_chat.return_value = mock_session

        # Define the sequence of LLM responses
        # 1. Initial response -> Call get_next_task
        resp_1 = MagicMock(spec=LLMResponse)
        resp_1.content = "I will check for tasks."
        resp_1.tool_calls = [{"id": "call_1", "function": {"name": "get_next_task", "arguments": "{}"}}]

        # 2. After get_next_task -> Call claim_task
        resp_2 = MagicMock(spec=LLMResponse)
        resp_2.content = "I see task 001. I will claim it."
        resp_2.tool_calls = [{"id": "call_2", "function": {"name": "claim_task", "arguments": '{"task_id": "001"}'}}]

        # 3. After claim_task -> Call write_file (Simulating the work)
        resp_3 = MagicMock(spec=LLMResponse)
        resp_3.content = "I will create the file."
        resp_3.tool_calls = [
            {
                "id": "call_3",
                "function": {
                    "name": "write_file",
                    "arguments": '{"path": "hello.txt", "content": "Hello World"}',
                },
            }
        ]

        # 4. After write_file -> Call complete_task
        resp_4 = MagicMock(spec=LLMResponse)
        resp_4.content = "File created. Completing task."
        resp_4.tool_calls = [{"id": "call_4", "function": {"name": "complete_task", "arguments": '{"task_id": "001"}'}}]

        # 5. After complete_task -> No tools (End loop)
        resp_5 = MagicMock(spec=LLMResponse)
        resp_5.content = "Task 001 completed."
        resp_5.tool_calls = []

        # Configure session.send to return these responses in order
        # Note: loop2.py calls session.send(user_msg) first, then run_loop calls session.send() repeatedly
        mock_session.send = AsyncMock(side_effect=[resp_1, resp_2, resp_3, resp_4, resp_5])

        # Run the orchestrator
        orchestrator = BlondieOrchestrator(str(temp_repo))

        await orchestrator.run()

        # --- Verification ---

        # 1. Verify file creation
        hello_file = temp_repo / "hello.txt"
        assert hello_file.exists()
        assert hello_file.read_text(encoding="utf-8") == "Hello World"

        # 2. Verify task completion in TASKS.md
        tasks_manager = TasksManager(temp_repo / ".agent" / "TASKS.md")
        task = next(t for t in tasks_manager.tasks if t.id == "001")
        assert task.status == TaskStatus.DONE

        # 3. Verify interaction flow
        assert mock_session.send.call_count == 5
