# tests/llm/test_llm_v2.py

"""LLM Router v2 tests (JSON output and Schema Validation)."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml
from pydantic import BaseModel

from agent.context import ContextGatherer
from agent.policy import Policy
from agent.router import LLMResponse, LLMRouter


@pytest.fixture
def mock_policy():
    """Mock policy for testing."""
    policy = MagicMock(spec=Policy)
    policy.check_permission.return_value = "allow"
    policy.limits = {}
    return policy


@pytest.mark.asyncio
async def test_plan_task_v2_json_parsing(mock_policy, tmp_path: Path):
    """Test that plan_task2 correctly parses JSON output."""
    # 1. Setup Config & Secrets
    secrets_file = tmp_path / "secrets.env.yaml"
    secrets_file.write_text("llm:\n  openai:\n    api_key: sk-test", encoding="utf-8")

    config_file = tmp_path / "llm_config.yaml"
    config_data = {
        "providers": {"openai": {"api_type": "openai"}},
        "operations": {"planning": [{"provider": "openai"}]},
    }
    config_file.write_text(yaml.dump(config_data), encoding="utf-8")

    # 2. Setup Skills Dir with plan_task2
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    skill_file = skills_dir / "plan_task2.skill.md"
    skill_content = """---
name: plan_task2
description: Generate detailed implementation plan.
operation: "planning"
input-schema:
  type: object
  properties:
    task_title: {type: string}
output-schema:
  type: object
  properties:
    implementation_plan: {type: string}
---
System prompt with {context}
"""
    skill_file.write_text(skill_content, encoding="utf-8")

    # 3. Mock LLM Response
    with patch("httpx.AsyncClient") as mock_client:
        mock_instance = mock_client.return_value
        mock_response = MagicMock()
        # Return valid JSON matching output-schema
        mock_response.json.return_value = {
            "choices": [{"message": {"content": '{"implementation_plan": "Step 1: Do it"}'}}],
            "usage": {"total_tokens": 100},
        }
        mock_instance.post = AsyncMock(return_value=mock_response)

        # 4. Initialize Router
        router = LLMRouter(secrets_file, config_file, mock_policy, skills_dir=skills_dir)

        # 5. Mock Context
        context_gatherer = MagicMock(spec=ContextGatherer)
        context_gatherer.gather.return_value = ("Context data", {})

        # 6. Execute Skill
        # pylint: disable-next=protected-access
        response = await router._execute_llm_skill("plan_task2", context_gatherer, task_title="Test Task")

        # 7. Assertions
        assert isinstance(response, LLMResponse)
        assert response.parsed is not None
        assert response.parsed["implementation_plan"] == "Step 1: Do it"

        # Ensure output schema was injected into prompt
        call_args = mock_instance.post.call_args
        assert call_args is not None
        sent_json = call_args[1]["json"]
        messages = sent_json["messages"]
        system_msg = messages[0]["content"]
        assert "## Output Format" in system_msg
        assert "implementation_plan" in system_msg


@pytest.mark.asyncio
async def test_plan_task_v2_validation_retry(mock_policy, tmp_path: Path):
    """Test that router retries on invalid JSON."""
    # Setup (reusing minimal setup)
    secrets_file = tmp_path / "secrets.env.yaml"
    secrets_file.write_text("llm:\n  openai:\n    api_key: sk-test", encoding="utf-8")
    config_file = tmp_path / "llm_config.yaml"
    config_file.write_text(
        yaml.dump(
            {"providers": {"openai": {"api_type": "openai"}}, "operations": {"planning": [{"provider": "openai"}]}}
        ),
        encoding="utf-8",
    )

    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    (skills_dir / "plan_task2.skill.md").write_text(
        """---
name: plan_task2
operation: "planning"
output-schema:
  type: object
  properties:
    plan: {type: string}
---
Prompt
""",
        encoding="utf-8",
    )

    with patch("httpx.AsyncClient") as mock_client:
        mock_instance = mock_client.return_value

        # First response: Invalid JSON
        bad_response = MagicMock()
        bad_response.json.return_value = {
            "choices": [{"message": {"content": "Not JSON"}}],
            "usage": {"total_tokens": 10},
        }

        # Second response: Valid JSON
        good_response = MagicMock()
        good_response.json.return_value = {
            "choices": [{"message": {"content": '{"plan": "Fixed"}'}}],
            "usage": {"total_tokens": 10},
        }

        # Mock post to return bad then good
        mock_instance.post = AsyncMock(side_effect=[bad_response, good_response])

        router = LLMRouter(secrets_file, config_file, mock_policy, skills_dir=skills_dir)
        context_gatherer = MagicMock(spec=ContextGatherer)
        context_gatherer.gather.return_value = ("", {})

        # pylint: disable-next=protected-access
        response = await router._execute_llm_skill("plan_task2", context_gatherer)

        assert response.parsed is not None
        assert response.parsed["plan"] == "Fixed"
        assert mock_instance.post.call_count == 2


@pytest.mark.asyncio
async def test_json_schema_validation_failure(mock_policy, tmp_path: Path):
    """Test retry on valid JSON that fails schema validation."""
    # Setup
    secrets_file = tmp_path / "secrets.env.yaml"
    secrets_file.write_text("llm:\n  openai:\n    api_key: sk-test", encoding="utf-8")
    config_file = tmp_path / "llm_config.yaml"
    config_file.write_text(
        yaml.dump(
            {"providers": {"openai": {"api_type": "openai"}}, "operations": {"planning": [{"provider": "openai"}]}}
        ),
        encoding="utf-8",
    )
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    (skills_dir / "schema_skill.skill.md").write_text(
        """---
name: schema_skill
operation: "planning"
output-schema:
  type: object
  properties:
    required_field: {type: string}
  required: [required_field]
---
Prompt
""",
        encoding="utf-8",
    )

    with patch("httpx.AsyncClient") as mock_client:
        mock_instance = mock_client.return_value
        # First response: valid JSON, but missing the required field
        bad_response = MagicMock()
        bad_response.json.return_value = {
            "choices": [{"message": {"content": '{"wrong_field": "value"}'}}],
            "usage": {"total_tokens": 10},
        }
        # Second response: valid JSON that matches the schema
        good_response = MagicMock()
        good_response.json.return_value = {
            "choices": [{"message": {"content": '{"required_field": "correct"}'}}],
            "usage": {"total_tokens": 10},
        }
        mock_instance.post = AsyncMock(side_effect=[bad_response, good_response])

        router = LLMRouter(secrets_file, config_file, mock_policy, skills_dir=skills_dir)
        context_gatherer = MagicMock(spec=ContextGatherer)
        context_gatherer.gather.return_value = ("", {})

        # pylint: disable-next=protected-access
        response = await router._execute_llm_skill("schema_skill", context_gatherer)
        assert response.parsed is not None
        assert response.parsed["required_field"] == "correct"
        assert mock_instance.post.call_count == 2


@pytest.mark.asyncio
async def test_chat_session_yaml_parsing(mock_policy, tmp_path: Path):
    """Test that ChatSession correctly parses YAML output."""
    secrets_file = tmp_path / "secrets.env.yaml"
    secrets_file.write_text("llm:\n  openai:\n    api_key: sk-test", encoding="utf-8")
    config_file = tmp_path / "llm_config.yaml"
    config_file.write_text(
        yaml.dump({"providers": {"openai": {"api_type": "openai"}}, "operations": {"test": [{"provider": "openai"}]}}),
        encoding="utf-8",
    )

    with patch("httpx.AsyncClient") as mock_client:
        mock_instance = mock_client.return_value
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "key: value\nlist:\n  - item"}}],
            "usage": {"total_tokens": 10},
        }
        mock_instance.post = AsyncMock(return_value=mock_response)

        router = LLMRouter(secrets_file, config_file, mock_policy)

        # pylint: disable-next=protected-access
        response = await router._execute_llm_task(
            "test", "System", "User", 0.1, 100, "test", "test", response_format="yaml"
        )

        assert response.parsed == {"key": "value", "list": ["item"]}


@pytest.mark.asyncio
async def test_chat_session_pydantic_validation(mock_policy, tmp_path: Path):
    """Test that ChatSession validates against Pydantic models."""

    class TestModel(BaseModel):
        """Pydantic model for testing."""

        name: str
        age: int

    secrets_file = tmp_path / "secrets.env.yaml"
    secrets_file.write_text("llm:\n  openai:\n    api_key: sk-test", encoding="utf-8")
    config_file = tmp_path / "llm_config.yaml"
    config_file.write_text(
        yaml.dump({"providers": {"openai": {"api_type": "openai"}}, "operations": {"test": [{"provider": "openai"}]}}),
        encoding="utf-8",
    )

    with patch("httpx.AsyncClient") as mock_client:
        mock_instance = mock_client.return_value
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": '{"name": "Alice", "age": 30}'}}],
            "usage": {"total_tokens": 10},
        }
        mock_instance.post = AsyncMock(return_value=mock_response)

        router = LLMRouter(secrets_file, config_file, mock_policy)

        # pylint: disable-next=protected-access
        response = await router._execute_llm_task(
            "test", "System", "User", 0.1, 100, "test", "test", response_schema=TestModel
        )

        assert isinstance(response.parsed, TestModel)
        assert response.parsed.name == "Alice"
        assert response.parsed.age == 30
