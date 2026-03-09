# tests/agent/test_router_retry.py

"""Tests for LLMRouter retry and fallback logic."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import yaml

from agent.llm_config import OperationSelection
from agent.router import LLMRouter


@pytest.fixture
def router_with_fallback(tmp_path):
    """Fixture for a router with two providers."""
    secrets_file = tmp_path / "secrets.env.yaml"
    secrets_file.write_text(
        """
llm:
  openai:
    api_key: sk-openai
  groq:
    api_key: sk-groq
"""
    )

    config_file = tmp_path / "llm_config.yaml"
    config_data = {
        "providers": {
            "openai": {"api_type": "openai", "default_model": "gpt-4"},
            "groq": {"api_type": "openai", "default_model": "llama3"},
        },
        "operations": {
            "testing": [
                {"provider": "openai"},
                {"provider": "groq", "model": "llama3"},
            ]
        },
    }
    config_file.write_text(yaml.dump(config_data))

    with patch("agent.router.LLMRouter._load_known_models", return_value=({}, {})):
        router = LLMRouter(secrets_file, config_file)
        router.journal = MagicMock()
        return router


@pytest.mark.asyncio
async def test_rate_limit_fallback(router_with_fallback):
    """Test that the router falls back to the next provider on a 429 error."""
    # 1. Mock the clients
    openai_client = router_with_fallback.clients["openai"]
    groq_client = router_with_fallback.clients["groq"]

    # OpenAI client will fail with a 429
    mock_429_response = httpx.Response(429, request=httpx.Request("POST", ""))

    # Groq client will succeed
    groq_response = MagicMock()
    groq_response.content = "Groq response"
    groq_response.tool_calls = None
    groq_response.cost_usd = 0.001

    with (
        patch.object(
            openai_client,
            "chat",
            side_effect=httpx.HTTPStatusError(
                "Rate limit exceeded", request=httpx.Request("POST", ""), response=mock_429_response
            ),
        ) as mock_openai_chat,
        patch.object(groq_client, "chat", return_value=groq_response) as mock_groq_chat,
    ):
        # 2. Execute a task
        # pylint: disable-next=protected-access
        response = await router_with_fallback._execute_llm_task(
            operation="testing",
            system_prompt="System",
            user_prompt="User",
            temperature=0.1,
            max_tokens=100,
            log_action="test",
            log_title="test",
        )

        # 3. Assertions
        assert response.content == "Groq response"
        mock_openai_chat.assert_called_once()
        mock_groq_chat.assert_called_once()

        # Check journal messages
        router_with_fallback.journal.print.assert_any_call("⚠️ Rate limit (429) exceeded for openai (gpt-4).")
        router_with_fallback.journal.print.assert_any_call("🔄 Switching to provider: groq (llama3)")


@pytest.mark.asyncio
async def test_rate_limit_wait_and_retry(router_with_fallback):
    """Test that the router waits and retries if no fallback is available."""
    # 1. Configure only one provider for the operation
    router_with_fallback.config.operations["testing"] = [OperationSelection(provider="openai", model="gpt-4")]

    # 2. Mock the client
    _openai_client = router_with_fallback.clients["openai"]

    # First call fails, second succeeds
    mock_429_response = httpx.Response(429, request=httpx.Request("POST", ""))
    success_response = MagicMock()
    success_response.content = "OpenAI response"
    success_response.tool_calls = None
    success_response.cost_usd = 0.002

    with patch(
        "llm.client.OpenAIClient.chat",
        side_effect=[
            httpx.HTTPStatusError("Rate limit exceeded", request=httpx.Request("POST", ""), response=mock_429_response),
            success_response,
        ],
    ) as mock_chat:
        # 3. Patch asyncio.sleep
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            # 4. Execute a task
            # pylint: disable-next=protected-access
            response = await router_with_fallback._execute_llm_task(
                operation="testing",
                system_prompt="System",
                user_prompt="User",
                temperature=0.1,
                max_tokens=100,
                log_action="test",
                log_title="test",
            )

            # 5. Assertions
            assert response.content == "OpenAI response"
            assert mock_chat.call_count == 2
            mock_sleep.assert_called_once_with(60)

            # Check journal messages
            router_with_fallback.journal.print.assert_any_call("⚠️ Rate limit (429) exceeded for openai (gpt-4).")
            router_with_fallback.journal.print.assert_any_call("⏳ No fallback available. Waiting 60s...")


def test_select_model_strict_config(router_with_fallback):
    """Test that select_model does not return unconfigured providers."""
    # Configure 'testing' to use ONLY openai
    router_with_fallback.config.operations["testing"] = [OperationSelection(provider="openai", model="gpt-4")]

    # Exclude openai (simulating rate limit)
    excluded = {("openai", "gpt-4")}

    # Even though 'groq' is available in router.clients, it should not be selected
    with pytest.raises(ValueError, match="No active LLM provider found"):
        router_with_fallback.select_model("testing", excluded_providers=excluded)


@pytest.fixture
def complex_router(tmp_path):
    """Router with complex config for fallback testing."""
    secrets_file = tmp_path / "secrets.env.yaml"
    # Secrets for openai, deepseek, groq. Anthropic missing.
    secrets_file.write_text(
        """
llm:
  openai:
    api_key: sk-openai
  deepseek:
    api_key: sk-deepseek
  groq:
    api_key: sk-groq
"""
    )

    config_file = tmp_path / "llm_config.yaml"
    config_data = {
        "providers": {
            "openai": {"api_type": "openai", "default_model": "gpt-4"},
            "anthropic": {"api_type": "anthropic", "default_model": "claude-3"},
            "groq": {"api_type": "openai", "default_model": "llama3"},
            "deepseek": {"api_type": "openai", "default_model": "deepseek-coder"},
        },
        "operations": {
            "planning": [
                {"provider": "openai"},
                {"provider": "anthropic"},
                {"provider": "groq"},
            ]
        },
    }
    config_file.write_text(yaml.dump(config_data))

    with patch("agent.router.LLMRouter._load_known_models", return_value=({}, {})):
        router = LLMRouter(secrets_file, config_file)
        router.journal = MagicMock()
        return router


def test_select_model_complex_fallback(complex_router):
    """Test fallback logic with missing keys and unconfigured providers."""
    # 1. First call: openai (first in list, has key)
    provider, _ = complex_router.select_model("planning")
    assert provider == "openai"

    # 2. Exclude openai: should skip anthropic (no key) and pick groq
    provider, _ = complex_router.select_model("planning", excluded_providers={("openai", "gpt-4")})
    assert provider == "groq"

    # 3. Exclude openai and groq: should fail. Deepseek has key but not in list.
    with pytest.raises(ValueError, match="No active LLM provider found"):
        complex_router.select_model("planning", excluded_providers={("openai", "gpt-4"), ("groq", "llama3")})


@pytest.mark.asyncio
async def test_rate_limit_fallback_same_provider(router_with_fallback):
    """Test fallback to another model within the same provider."""
    # Configure operations: openai (gpt-4) -> openai (gpt-3.5)
    router_with_fallback.config.operations["testing"] = [
        OperationSelection(provider="openai", model="gpt-4"),
        OperationSelection(provider="openai", model="gpt-3.5"),
    ]

    openai_client = router_with_fallback.clients["openai"]

    mock_429 = httpx.Response(429, request=httpx.Request("POST", ""))
    mock_success = MagicMock()
    mock_success.content = "Success"
    mock_success.tool_calls = None
    mock_success.cost_usd = 0.01

    async def side_effect(messages, **kwargs):
        model = kwargs.get("model")
        if model == "gpt-4":
            raise httpx.HTTPStatusError("Rate limit", request=None, response=mock_429)
        if model == "gpt-3.5":
            return mock_success
        raise ValueError(f"Unexpected model {model}")

    with patch.object(openai_client, "chat", side_effect=side_effect) as mock_chat:
        response = await router_with_fallback._execute_llm_task(
            operation="testing",
            system_prompt="Sys",
            user_prompt="User",
            temperature=0.1,
            max_tokens=100,
            log_action="test",
            log_title="test",
        )

        assert response.content == "Success"
        assert mock_chat.call_count == 2

        # Verify logs
        router_with_fallback.journal.print.assert_any_call("⚠️ Rate limit (429) exceeded for openai (gpt-4).")
        router_with_fallback.journal.print.assert_any_call("🔄 Switching to provider: openai (gpt-3.5)")
