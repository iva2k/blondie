# tests/llm/test_client.py

"""Unit tests for LLM Clients."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from llm.client import AnthropicClient, OpenAIClient


@pytest.mark.asyncio
async def test_openai_chat():
    """Test OpenAI client chat."""
    client = OpenAIClient("key", "url", "gpt-4")
    client.client.post = AsyncMock()

    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": "Hello", "tool_calls": None}}],
        "usage": {"total_tokens": 10, "prompt_tokens": 5, "completion_tokens": 5},
    }
    client.client.post.return_value = mock_resp

    response = await client.chat([{"role": "user", "content": "Hi"}])

    assert response.content == "Hello"
    assert response.tokens_used == 10


@pytest.mark.asyncio
async def test_anthropic_chat():
    """Test Anthropic client chat message formatting."""
    client = AnthropicClient("key", "url", "claude-3")
    client.client.post = AsyncMock()

    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "content": [{"type": "text", "text": "Hello"}],
        "usage": {"input_tokens": 5, "output_tokens": 5},
    }
    client.client.post.return_value = mock_resp

    # Test message conversion
    messages = [
        {"role": "system", "content": "Sys"},
        {"role": "user", "content": "Hi"},
        {"role": "tool", "tool_call_id": "123", "content": "Result"},
    ]

    await client.chat(messages)

    # Verify payload structure
    call_args = client.client.post.call_args
    payload = call_args[1]["json"]

    assert payload["system"] == "Sys"
    assert len(payload["messages"]) == 2
    # User message
    assert payload["messages"][0]["role"] == "user"
    assert payload["messages"][0]["content"] == "Hi"
    # Tool result mapped to user role
    assert payload["messages"][1]["role"] == "user"
    assert payload["messages"][1]["content"][0]["type"] == "tool_result"
    assert payload["messages"][1]["content"][0]["tool_use_id"] == "123"


@pytest.mark.asyncio
async def test_anthropic_cost_calculation():
    """Test Anthropic cost calculation."""
    pricing = {"claude-3": {"input": 10.0, "output": 30.0}}  # $10/$30 per M
    client = AnthropicClient("key", "url", "claude-3", pricing=pricing)
    client.client.post = AsyncMock()

    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "content": [{"type": "text", "text": "Hi"}],
        "usage": {"input_tokens": 1_000_000, "output_tokens": 1_000_000},
    }
    client.client.post.return_value = mock_resp

    response = await client.chat([{"role": "user", "content": "Hi"}])

    # 1M input * $10 + 1M output * $30 = $40
    assert response.cost_usd == 40.0


@pytest.mark.asyncio
async def test_anthropic_tool_calls_parsing():
    """Test parsing of Anthropic tool calls."""
    client = AnthropicClient("key", "url", "claude-3")
    client.client.post = AsyncMock()

    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "content": [{"type": "tool_use", "id": "call_1", "name": "test_tool", "input": {"arg": "val"}}],
        "usage": {},
    }
    client.client.post.return_value = mock_resp

    response = await client.chat([{"role": "user", "content": "Hi"}])

    assert response.tool_calls is not None
    assert response.tool_calls[0]["function"]["name"] == "test_tool"
    assert response.tool_calls[0]["function"]["arguments"] == '{"arg": "val"}'


@pytest.mark.asyncio
async def test_openai_list_models():
    """Test OpenAI list_models."""
    client = OpenAIClient("key", "url", "model")
    mock_response = MagicMock()
    mock_response.json.return_value = {"data": [{"id": "gpt-4"}, {"id": "gpt-3.5"}]}
    client.client.get = AsyncMock(return_value=mock_response)

    models = await client.list_models()
    assert "gpt-4" in models
    assert len(models) == 2


@pytest.mark.asyncio
async def test_anthropic_list_models():
    """Test Anthropic list_models."""
    client = AnthropicClient("key", "url", "model")
    mock_response = MagicMock()
    mock_response.json.return_value = {"data": [{"id": "claude-3"}, {"id": "claude-2"}]}
    client.client.get = AsyncMock(return_value=mock_response)

    models = await client.list_models()
    assert "claude-3" in models
    assert len(models) == 2
