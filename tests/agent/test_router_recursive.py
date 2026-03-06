# tests/agent/test_router_recursive.py

"""Unit tests for recursive router logic."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.router import ChatSession, LLMRouter
from llm.client import LLMResponse
from llm.skill import Skill


@pytest.fixture
def mock_router(tmp_path):
    """Create an LLMRouter with mocked internals and skills."""
    secrets_file = tmp_path / "secrets.yaml"
    secrets_file.write_text("llm: {}", encoding="utf-8")
    config_file = tmp_path / "config.yaml"
    config_file.write_text("providers: {}\noperations: {}", encoding="utf-8")

    with (
        patch("agent.router.LLMRouter._load_secrets", return_value={}),
        patch("agent.router.LLMRouter._load_known_models", return_value=({}, {})),
        patch("agent.router.LLMRouter._init_clients"),
    ):
        router = LLMRouter(secrets_file, config_file)

        # Add some mock skills
        skill_v1 = MagicMock(spec=Skill)
        skill_v1.name = "skill_v1"
        skill_v1.input_schema = None  # v1 skill (no schema)

        skill_v2 = MagicMock(spec=Skill)
        skill_v2.name = "skill_v2"
        skill_v2.input_schema = {"type": "object"}  # v2 skill
        skill_v2.to_tool_definition.return_value = {"name": "skill_v2", "parameters": {}}

        router.skills = {"skill_v1": skill_v1, "skill_v2": skill_v2}  # type: ignore

        return router


def test_register_skills(mock_router):
    """Test that only v2 skills are registered as tools."""
    tool_handler = MagicMock()
    context_gatherer = MagicMock()

    mock_router.register_skills(tool_handler, context_gatherer)

    # Should only register v2 skill
    assert tool_handler.register.call_count == 1
    args = tool_handler.register.call_args
    assert args[0][0] == "skill_v2"
    assert args[0][1] == {"name": "skill_v2", "parameters": {}}
    # Check if implementation is callable
    assert callable(args[0][2])


@pytest.mark.asyncio
async def test_execute_skill_as_tool(mock_router):
    """Test recursive execution flow."""
    tool_handler = MagicMock()
    context_gatherer = MagicMock()

    # Mock start_chat and session
    mock_session = MagicMock(spec=ChatSession)
    mock_session.user_content = "User Prompt"
    mock_session.send = AsyncMock()
    mock_session.send.return_value.content = "Initial Response"

    mock_router.start_chat = MagicMock(return_value=mock_session)

    # Mock tool_handler.run_loop
    tool_handler.run_loop = AsyncMock()
    tool_handler.run_loop.return_value.content = "Final Result"

    result = await mock_router.execute_skill_as_tool("skill_v2", context_gatherer, tool_handler, arg1="val1")

    assert result == "Final Result"
    mock_router.start_chat.assert_called_with("skill_v2", context_gatherer, arg1="val1")
    mock_session.send.assert_called_with(prompt="User Prompt")
    tool_handler.run_loop.assert_called()


@pytest.mark.asyncio
async def test_execute_skill_as_tool_failure(mock_router):
    """Test that exceptions during sub-agent execution are handled."""
    tool_handler = MagicMock()
    context_gatherer = MagicMock()

    # Make start_chat fail
    mock_router.start_chat = MagicMock(side_effect=ValueError("Skill init failed"))

    # The implementation of the skill-as-a-tool should catch this
    mock_router.register_skills(tool_handler, context_gatherer)
    skill_impl = tool_handler.register.call_args[0][2]

    with pytest.raises(ValueError, match="Skill init failed"):
        await skill_impl()


def test_start_chat_unknown_tool(mock_router):
    """Test that a warning is logged for unknown tools in a skill."""
    # Setup mocks to pass select_model and client checks
    mock_router.skills["skill_v2"].operation = "planning"
    mock_router.skills["skill_v2"].user_content = "User prompt"
    mock_router.select_model = MagicMock(return_value=("mock_provider", "mock_model"))
    mock_router.clients = {"mock_provider": MagicMock()}

    mock_router.skills["skill_v2"].tools = ["run_shell", "unknown_tool"]
    mock_router.journal = MagicMock()

    # This should not raise an error, just log a warning
    session = mock_router.start_chat("skill_v2")

    assert session is not None
    # Verify that the known tool is present
    assert any(t["name"] == "run_shell" for t in session.tools)
    # Verify the warning was printed
    mock_router.journal.print.assert_called_with("⚠️ Unknown tool 'unknown_tool' in skill 'skill_v2'")


@pytest.mark.asyncio
async def test_generate_code2_side_effect(mock_router):
    """Test that generate_code2 skill correctly calls write_file tool."""
    tool_handler = MagicMock()
    context_gatherer = MagicMock()

    # 1. Mock the `generate_code2` skill
    gen_code_skill = MagicMock(spec=Skill)
    gen_code_skill.name = "generate_code2"
    gen_code_skill.input_schema = {"type": "object"}
    gen_code_skill.to_tool_definition.return_value = {"name": "generate_code2", "parameters": {}}
    gen_code_skill.user_content = "User prompt for generate_code2"
    mock_router.skills = {"generate_code2": gen_code_skill}  # type: ignore

    # 2. Mock the LLM response *for the sub-agent*
    # This response will contain the tool call to `write_file`
    sub_agent_response = MagicMock(spec=LLMResponse)
    sub_agent_response.tool_calls = [
        {"id": "call_write", "function": {"name": "write_file", "arguments": '{"path": "a.py", "content": "print(1)"}'}}
    ]

    # 3. Mock the session that `execute_skill_as_tool` will create
    mock_session = MagicMock(spec=ChatSession)
    mock_session.user_content = "User prompt for generate_code2"
    mock_session.send = AsyncMock(return_value=sub_agent_response)
    mock_router.start_chat = MagicMock(return_value=mock_session)

    # 4. Mock the tool_handler's run_loop to just return a final summary
    tool_handler.run_loop = AsyncMock()
    tool_handler.run_loop.return_value.content = '{"summary": "File written", "status": "SUCCESS"}'

    # 5. Execute the skill-as-a-tool
    await mock_router.execute_skill_as_tool("generate_code2", context_gatherer, tool_handler)

    # 6. Assert that the sub-agent's tool loop was called correctly
    tool_handler.run_loop.assert_called_once()
    # The first argument to run_loop is the session, the second is the response containing the tool call
    assert tool_handler.run_loop.call_args[0][1] == sub_agent_response
