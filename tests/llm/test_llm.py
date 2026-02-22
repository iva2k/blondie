# tests/llm/test_llm.py

"""Basic LLM router tests."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent.policy import Policy
from llm.router import LLMResponse, LLMRouter


@pytest.fixture
def mock_secrets():
    """Mock secrets for testing."""
    return {"llm": {"openai": {"api_key": "sk-test", "model": "gpt-4o-mini"}}}


@pytest.fixture
def mock_policy():
    """Mock policy for testing."""
    policy = MagicMock(spec=Policy)
    policy.check_permission.return_value = "allow"
    return policy


def test_router_initialization(mock_secrets, mock_policy, tmp_path: Path):
    """Initialize router for testing."""
    secrets_file = tmp_path / "secrets.yaml"
    secrets_file.write_text(str(mock_secrets))

    with patch("pathlib.Path.read_text", return_value=str(mock_secrets)):
        router = LLMRouter(secrets_file, mock_policy)

    assert "openai" in router.clients
    assert router.clients["openai"].model == "gpt-4o-mini"


@pytest.mark.asyncio
async def test_plan_task(mock_policy, tmp_path: Path):
    """Test task planning."""
    # mock_secrets = {"llm": {"openai": {"api_key": "sk-test"}}}
    # Create a real temporary secrets file with YAML content
    secrets_file = tmp_path / "secrets.env.yaml"
    secrets_file.write_text("llm:\n  openai:\n    api_key: sk-test", encoding="utf-8")

    with (
        # Remove patch("pathlib.Path.read_text") as we use a real file now
        # patch("pathlib.Path.read_text", return_value=str(mock_secrets)),
        patch("httpx.AsyncClient.post") as mock_post
    ):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Plan: step 1"}}],
            "usage": {"total_tokens": 100},
        }
        mock_post.return_value = mock_response

        router = LLMRouter(secrets_file, mock_policy)
        with patch.object(router, "select_model", return_value="openai"):
            response = await router.plan_task("test task", "context", {})

        assert isinstance(response, LLMResponse)
        assert "Plan:" in response.content
