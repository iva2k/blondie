# tests/llm/test_skill.py

"""Unit tests for Skill module."""

import json
from pathlib import Path

import pytest

from llm.skill import Skill


def test_from_file_valid(tmp_path):
    """Test loading a valid skill file."""
    f = tmp_path / "skill.md"
    f.write_text(
        """---
name: test_skill
description: A test skill
input-schema:
  type: object
---
System Prompt {{var}}""",
        encoding="utf-8",
    )

    skill = Skill.from_file(f)
    assert skill.name == "test_skill"
    assert skill.description == "A test skill"
    assert skill.system_prompt == "System Prompt {{var}}"
    assert skill.input_schema == {"type": "object"}


def test_from_file_missing():
    """Test loading a non-existent skill file."""
    with pytest.raises(FileNotFoundError):
        Skill.from_file(Path("nonexistent.md"))


def test_from_file_invalid_format(tmp_path):
    """Test loading a skill file with invalid format."""
    f = tmp_path / "bad.md"
    f.write_text("No frontmatter", encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid skill file"):
        Skill.from_file(f)


def test_render_system_prompt():
    """Test rendering the system prompt with context variables."""
    skill = Skill(name="n", description="d", system_prompt="Hello {name}", user_content=None)
    assert skill.render_system_prompt(name="World") == "Hello World"


def test_render_system_prompt_missing_arg():
    """Test rendering failure when variables are missing."""
    skill = Skill(name="n", description="d", system_prompt="Hello {name}", user_content=None)
    with pytest.raises(ValueError, match="Missing context variable"):
        skill.render_system_prompt()


def test_render_system_prompt_with_output_schema():
    """Test that output schema is appended to system prompt."""
    schema = {"type": "object", "properties": {"res": {"type": "string"}}}
    skill = Skill(name="n", description="d", system_prompt="Prompt", user_content=None, output_schema=schema)

    rendered = skill.render_system_prompt()
    assert "Prompt" in rendered
    assert "## Output Format" in rendered
    assert json.dumps(schema, indent=2) in rendered


def test_to_tool_definition():
    """Test conversion to tool definition."""
    schema = {"type": "object"}
    skill = Skill(name="my_tool", description="desc", system_prompt="", user_content=None, input_schema=schema)

    tool_def = skill.to_tool_definition()
    assert tool_def["name"] == "my_tool"
    assert tool_def["description"] == "desc"
    assert tool_def["parameters"] == schema
