# tests/agent/test_project.py

"""Unit tests for Project configuration parser."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from agent.project import Project


@pytest.fixture
def sample_project_yaml(tmp_path: Path) -> Path:
    """Create a sample project.yaml file."""
    content = """
id: blondie-test
name: "Test Project"
languages: [python, rust]
task_source: TASKS.md
commands:
  test: pytest
policy: POLICY.yaml
docs: [README.md]
deploy:
  docker: docker build .
git_user: "Test Bot"
git_email: "bot@test.com"
"""
    f = tmp_path / "project.yaml"
    f.write_text(content, encoding="utf-8")
    return f


def test_project_parsing(sample_project_yaml: Path) -> None:
    """Test parsing a valid project.yaml."""
    project = Project.from_file(sample_project_yaml)

    assert project.id == "blondie-test"
    assert project.name == "Test Project"
    assert project.languages == ["python", "rust"]
    assert project.commands["test"] == "pytest"
    assert project.get_command("test") == "pytest"
    assert project.deploy["docker"] == "docker build ."
    assert project.git_user == "Test Bot"
    assert project.git_email == "bot@test.com"


def test_project_defaults(tmp_path: Path) -> None:
    """Test default values for optional fields."""
    f = tmp_path / "minimal.yaml"
    f.write_text("id: minimal", encoding="utf-8")

    project = Project.from_file(f)

    assert project.id == "minimal"
    assert project.name is None
    assert project.languages == []
    assert project.task_source == "TASKS.md"
    assert project.policy == "POLICY.yaml"
    assert project.commands == {}
    assert project.git_user is None
    assert project.git_email is None
    assert project.sleep_daily_limit == 3600


def test_file_not_found(tmp_path: Path) -> None:
    """Test handling of missing file."""
    with pytest.raises(FileNotFoundError):
        Project.from_file(tmp_path / "nonexistent.yaml")


def test_validation_error(tmp_path: Path) -> None:
    """Test validation of required fields."""
    f = tmp_path / "invalid.yaml"
    f.write_text("name: No ID here", encoding="utf-8")

    with pytest.raises(ValidationError):
        Project.from_file(f)
