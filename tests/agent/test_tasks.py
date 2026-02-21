"""Unit tests for TASKS.md parser."""

from pathlib import Path

import pytest

from agent.tasks import TasksManager, TaskStatus


@pytest.fixture
def sample_tasks_content() -> str:
    """Create sample TASKS.md content."""
    return """# Blondie Tasks

## Done
- [x] 001 | P0 | Policy parser |

## Todo
- [ ] 002 | P1 | TASKS.md parser |
- [ ] 003 | P0 | Git CLI wrapper | 001, 002
- [ ] 004 | P2 | LLM router |
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
    t1 = next(t for t in manager.tasks if t.id == "001")
    assert t1.status == TaskStatus.DONE
    assert t1.priority == "P0"
    assert t1.branch_name == "task-blondie-001"

    # Check Todo task
    t2 = next(t for t in manager.tasks if t.id == "002")
    assert t2.status == TaskStatus.TODO
    assert t2.priority == "P1"


def test_get_todo_tasks_priority(tasks_file: Path) -> None:
    """Test that todos are sorted by priority."""
    manager = TasksManager(tasks_file)
    todos = manager.get_todo_tasks()
    assert len(todos) == 3
    # P0 should be first
    assert todos[0].id == "003"
    assert todos[1].id == "002"
    assert todos[2].id == "004"


def test_complete_task(tasks_file: Path) -> None:
    """Test completing a task."""
    manager = TasksManager(tasks_file)
    success = manager.complete_task("002")
    assert success

    t2 = next(t for t in manager.tasks if t.id == "002")
    assert t2.status == TaskStatus.DONE


def test_missing_file(tmp_path: Path) -> None:
    """Test graceful handling of missing file."""
    manager = TasksManager(tmp_path / "missing.md")
    assert len(manager.tasks) == 0
