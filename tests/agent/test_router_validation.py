# tests/agent/test_router_validation.py

"""Tests for LLMRouter schema validation retry logic."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import BaseModel, Field

from agent.router import ChatSession
from llm.client import LLMResponse


class SimpleSchema(BaseModel):
    """A simple Pydantic model for testing."""

    name: str
    value: int = Field(..., gt=0)


@pytest.fixture
def chat_session():
    """Fixture for a ChatSession with a schema."""
    mock_client = MagicMock()
    mock_client.chat = AsyncMock()

    session = ChatSession(
        client=mock_client,
        provider_name="test_provider",
        model="test_model",
        journal=MagicMock(),
        cost_callback=MagicMock(),
        system_prompt="System",
        temperature=0.1,
        max_tokens=100,
        log_action="test",
        log_title="test",
        response_schema=SimpleSchema,
    )
    return session


@pytest.mark.asyncio
async def test_validation_retry_and_succeed(chat_session):
    """Test that the session retries on validation error and then succeeds."""
    # First response: invalid JSON
    invalid_response = LLMResponse(content='{"name": "test", "value": -5}', model="test", tokens_used=10)
    # Second response: valid JSON
    valid_response = LLMResponse(content='{"name": "test", "value": 10}', model="test", tokens_used=10)

    chat_session.client.chat.side_effect = [invalid_response, valid_response]

    response = await chat_session.send("User prompt")

    # Assertions
    assert chat_session.client.chat.call_count == 2
    assert response.parsed is not None
    assert isinstance(response.parsed, SimpleSchema)
    assert response.parsed.value == 10

    # Check that an error message was added to the history for the retry
    assert len(chat_session.messages) == 5  # System, User, Assistant (fail), User (error), Assistant (ok)
    assert chat_session.messages[3]["role"] == "user"
    assert "Error parsing response" in chat_session.messages[3]["content"]
    assert "Input should be greater than 0" in chat_session.messages[3]["content"]


@pytest.mark.asyncio
async def test_validation_fail_after_max_retries(chat_session):
    """Test that the session fails after max retries."""
    # All responses are invalid
    invalid_response1 = LLMResponse(content="{invalid json}", model="test", tokens_used=10)
    invalid_response2 = LLMResponse(content='{"name": "test"}', model="test", tokens_used=10)
    invalid_response3 = LLMResponse(content='{"name": "test", "value": 0}', model="test", tokens_used=10)
    invalid_response4 = LLMResponse(content='{"name": "test", "value": -1}', model="test", tokens_used=10)

    chat_session.client.chat.side_effect = [
        invalid_response1,
        invalid_response2,
        invalid_response3,
        invalid_response4,
    ]

    response = await chat_session.send("User prompt")

    # Assertions
    assert chat_session.client.chat.call_count == 4  # 1 initial + 3 retries
    # When validation fails but JSON parsing succeeds, parsed contains the raw dict
    assert response.parsed == {"name": "test", "value": -1}
    assert response.content == invalid_response4.content  # Returns the last invalid response

    # Check journal logs
    found_error = False
    for call in chat_session.journal.print.call_args_list:
        arg = call.args[0]
        if "❌ Validation failed after 3 retries" in arg and "Input should be greater than 0" in arg:
            found_error = True
            break
    assert found_error, "Validation failure message not found in journal"
