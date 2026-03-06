# tests/llm/test_skill.py

"""Unit tests for Skill parser."""

import pytest

from llm.skill import FileEdits, Skill


@pytest.fixture
def mock_skill_file(tmp_path):
    """Create a sample skill file for testing."""

    content = """---
name: test_skill
description: A test skill
input-schema:
  type: object
  properties:
    arg1: {type: string}
output-schema:
  type: object
  properties:
    result: {type: string}
---
System prompt with {var}
"""
    f = tmp_path / "test.skill.md"
    f.write_text(content, encoding="utf-8")
    return f


def test_skill_parsing(mock_skill_file):
    """Test basic skill parsing."""
    skill = Skill.from_file(mock_skill_file)
    assert skill.name == "test_skill"
    assert skill.input_schema == {"type": "object", "properties": {"arg1": {"type": "string"}}}
    assert skill.output_schema == {"type": "object", "properties": {"result": {"type": "string"}}}


def test_render_system_prompt(mock_skill_file):
    """Test system prompt rendering with variables and schema injection."""
    skill = Skill.from_file(mock_skill_file)
    prompt = skill.render_system_prompt(var="value")
    assert "System prompt with value" in prompt
    assert "## Output Format" in prompt
    assert "valid JSON object matching this schema" in prompt
    assert '"result": {' in prompt


def test_to_tool_definition(mock_skill_file):
    """Test conversion to tool definition."""
    skill = Skill.from_file(mock_skill_file)
    tool_def = skill.to_tool_definition()
    assert tool_def["name"] == "test_skill"
    assert tool_def["description"] == "A test skill"
    assert tool_def["parameters"] == skill.input_schema


def test_render_system_prompt_missing_var(mock_skill_file):
    """Test error when context variable is missing."""
    skill = Skill.from_file(mock_skill_file)
    with pytest.raises(ValueError, match="Missing context variable"):
        skill.render_system_prompt()


def test_file_not_found(tmp_path):
    """Test loading a non-existent file."""
    with pytest.raises(FileNotFoundError):
        Skill.from_file(tmp_path / "nonexistent.md")


def test_invalid_format_missing_frontmatter(tmp_path):
    """Test loading a file without frontmatter separators."""
    f = tmp_path / "bad.md"
    f.write_text("Just some text", encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid skill file format"):
        Skill.from_file(f)


def test_invalid_yaml(tmp_path):
    """Test loading a file with invalid YAML frontmatter."""
    content = """---
name: test
  indentation_error: true
---
Prompt
"""
    f = tmp_path / "bad_yaml.md"
    f.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid YAML frontmatter"):
        Skill.from_file(f)


def test_default_values(tmp_path):
    """Test default values for optional fields."""
    content = """---
name: minimal
---
Prompt
"""
    f = tmp_path / "minimal.md"
    f.write_text(content, encoding="utf-8")
    skill = Skill.from_file(f)

    assert skill.name == "minimal"
    assert skill.description == ""
    assert skill.operation == "coding"
    assert skill.temperature == pytest.approx(0.1)
    assert skill.max_tokens == 2000
    assert skill.tools is None
    assert skill.input_schema is None
    assert skill.output_schema is None


def test_response_schema_mapping(tmp_path):
    """Test mapping response-schema string to Pydantic model."""
    content = """---
name: schema_test
response-schema: FileEdits
---
Prompt
"""
    f = tmp_path / "schema.md"
    f.write_text(content, encoding="utf-8")
    skill = Skill.from_file(f)

    assert skill.response_schema == FileEdits
