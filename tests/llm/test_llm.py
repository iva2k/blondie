# tests/llm/test_llm.py

"""Basic LLM router tests."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml

from agent.context import ContextGatherer
from agent.policy import Policy
from agent.router import LLMResponse, LLMRouter


@pytest.fixture
def mock_secrets():
    """Mock secrets for testing."""
    return {"llm": {"openai": {"api_key": "sk-test", "model": "gpt-4o-mini"}}}


@pytest.fixture
def mock_policy():
    """Mock policy for testing."""
    policy = MagicMock(spec=Policy)
    policy.check_permission.return_value = "allow"
    policy.limits = {}
    return policy


def test_router_initialization(mock_secrets, mock_policy, tmp_path: Path):
    """Initialize router for testing."""
    secrets_file = tmp_path / "secrets.yaml"
    secrets_file.write_text(yaml.dump(mock_secrets), encoding="utf-8")

    config_file = tmp_path / "llm_config.yaml"
    config_data = {"providers": {"openai": {"api_type": "openai", "default_model": "gpt-4o-mini"}}}
    config_file.write_text(yaml.dump(config_data), encoding="utf-8")

    with patch("httpx.AsyncClient"):
        router = LLMRouter(secrets_file, config_file, mock_policy)

    assert "openai" in router.clients
    assert router.clients["openai"].model == "gpt-4o-mini"


@pytest.mark.asyncio
async def test_plan_task(mock_policy, tmp_path: Path):
    """Test task planning."""
    secrets_file = tmp_path / "secrets.env.yaml"
    secrets_file.write_text("llm:\n  openai:\n    api_key: sk-test", encoding="utf-8")

    config_file = tmp_path / "llm_config.yaml"
    config_data = {
        "providers": {"openai": {"api_type": "openai", "default_model": "gpt-4"}},
        "operations": {"planning": [{"provider": "openai"}]},
    }
    config_file.write_text(yaml.dump(config_data), encoding="utf-8")

    with patch("httpx.AsyncClient") as mock_client:
        mock_instance = mock_client.return_value
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Plan: step 1"}}],
            "usage": {"total_tokens": 100},
        }
        mock_instance.post = AsyncMock(return_value=mock_response)

        router = LLMRouter(secrets_file, config_file, mock_policy)
        context_gatherer = MagicMock(spec=ContextGatherer)
        context_gatherer.gather.return_value = (
            "context",
            {"task_id": "001", "task_title": "Dummy task", "task_priority": "P1"},
        )
        context_gatherer.add_task(None)
        response = await router.plan_task(context_gatherer)

        assert isinstance(response, LLMResponse)
        assert "Plan: step 1" in response.content
