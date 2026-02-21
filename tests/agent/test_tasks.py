"""Unit tests for TASKS.md parser."""

from pathlib import Path

import pytest

from agent.tasks import TasksManager, TaskStatus


@pytest.fixture
def sample_tasks_content() -> str:
    """Create sample TASKS.md content."""
    return """# Blondie Tasks

## Done
- [x] P0 | BLONDIE-001 | Policy parser | main

## In Progress
- [ ] P1 | BLONDIE-002 | TASKS.md parser | task-BLONDIE-002

## Todo
- [ ] P0 | BLONDIE-003 | Git CLI wrapper |
- [ ] P2 | BLONDIE-004 | LLM router |
"""


@pytest.fixture
def tasks_file(tmp_path: Path, sample_tasks_content: str) -> Path:
    """Create a temporary TASKS.md file."""
    f = tmp_path / "TASKS.md"
    f.write_text(sample_tasks_content, encoding="utf-8")
    return f


def test_parse_tasks(tasks_file: Path) -> None:
    """Test parsing of existing tasks."""
    manager = TasksManager(tasks_file)
    assert len(manager.tasks) == 4

    # Check Done task
    t1 = next(t for t in manager.tasks if t.id == "BLONDIE-001")
    assert t1.status == TaskStatus.DONE
    assert t1.priority == "P0"
    assert t1.branch == "main"

    # Check In Progress task
    t2 = next(t for t in manager.tasks if t.id == "BLONDIE-002")
    assert t2.status == TaskStatus.IN_PROGRESS
    assert t2.priority == "P1"


def test_get_todo_tasks_priority(tasks_file: Path) -> None:
    """Test that todos are sorted by priority."""
    manager = TasksManager(tasks_file)
    todos = manager.get_todo_tasks()
    assert len(todos) == 2
    # P0 should be first
    assert todos[0].id == "BLONDIE-003"
    assert todos[1].id == "BLONDIE-004"


def test_claim_task(tasks_file: Path) -> None:
    """Test claiming a task updates status and file."""
    manager = TasksManager(tasks_file)
    task = manager.claim_task("BLONDIE-003")

    assert task is not None
    assert task.status == TaskStatus.IN_PROGRESS
    assert task.branch == "blondie-003"  # Derived from ID

    # Verify persistence
    content = tasks_file.read_text(encoding="utf-8")
    assert "BLONDIE-003" in content


def test_complete_task(tasks_file: Path) -> None:
    """Test completing a task."""
    manager = TasksManager(tasks_file)
    success = manager.complete_task("BLONDIE-002")
    assert success

    t2 = next(t for t in manager.tasks if t.id == "BLONDIE-002")
    assert t2.status == TaskStatus.DONE


def test_missing_file(tmp_path: Path) -> None:
    """Test graceful handling of missing file."""
    manager = TasksManager(tmp_path / "missing.md")
    assert len(manager.tasks) == 0
