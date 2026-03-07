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
