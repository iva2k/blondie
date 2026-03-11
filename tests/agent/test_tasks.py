# tests/agent/test_tasks.py

"""Unit tests for TASKS.md parser."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from agent.tasks import Task, TasksManager, TaskStatus


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
    success, _ = manager.complete_task("002")
    assert success

    t2 = next(t for t in manager.tasks if t.id == "002")
    assert t2.status == TaskStatus.DONE


def test_claim_task_success(tasks_file: Path) -> None:
    """Test claiming a task successfully."""
    manager = TasksManager(tasks_file)
    mock_git = MagicMock()
    # Setup git mocks for success path
    # 1. Check local ownership -> False
    mock_git.branch_exists.return_value = False
    # 2. Check remote lock -> False
    mock_git.remote_branch_exists.return_value = False

    success, msg = manager.claim_task("002", mock_git)

    assert success
    assert "Successfully claimed" in msg
    mock_git.checkout_branch.assert_called_with("task-blondie-002")
    mock_git.push.assert_called_with("task-blondie-002")


def test_claim_task_already_claimed_remote(tasks_file: Path) -> None:
    """Test claiming a task that exists on remote."""
    manager = TasksManager(tasks_file)
    mock_git = MagicMock()
    mock_git.branch_exists.return_value = False
    mock_git.remote_branch_exists.return_value = True

    success, msg = manager.claim_task("002", mock_git)

    assert not success
    assert "already claimed" in msg


def test_get_task_fuzzy(tasks_file: Path) -> None:
    """Test fuzzy ID matching."""
    manager = TasksManager(tasks_file)

    # Exact
    t1 = manager.get_task("001")
    assert t1 is not None and t1.id == "001"

    # Full ID
    t2 = manager.get_task("BLONDIE-001")
    assert t2 is not None and t2.id == "001"

    # "Task 001"
    t3 = manager.get_task("Task 001")
    assert t3 is not None and t3.id == "001"


def test_missing_file(tmp_path: Path) -> None:
    """Test graceful handling of missing file."""
    manager = TasksManager(tmp_path / "missing.md")
    assert len(manager.tasks) == 0


@pytest.mark.parametrize(
    "line, expected_id, expected_priority, expected_title, expected_deps",
    [
        ("- [ ] 123 | P1 | Simple task |", "123", "P1", "Simple task", []),
        ("* [ ] ABC | | Task with no priority | 123", "ABC", None, "Task with no priority", ["123"]),
        ("  - [x] 456 | P2 | Done task with spaces | 1,2, 3", "456", "P2", "Done task with spaces", ["1", "2", "3"]),
        ("[ ] 789||Another task|", "789", None, "Another task", []),
        ("- [ ] TSK10 | HIGH | High priority |", "TSK10", "HIGH", "High priority", []),
    ],
)
def test_parse_various_formats(
    tmp_path: Path, line: str, expected_id: str, expected_priority: str, expected_title: str, expected_deps: list[str]
) -> None:
    """Test parsing of various valid task line formats."""
    content = f"## Todo\n{line}"
    tasks_file = tmp_path / "TASKS.md"
    tasks_file.write_text(content, encoding="utf-8")

    manager = TasksManager(tasks_file)
    assert len(manager.tasks) == 1
    task = manager.tasks[0]
    assert task.id == expected_id
    assert task.priority == expected_priority
    assert task.title == expected_title
    assert task.depends_on == expected_deps


def test_print_summary(tasks_file):
    """Test summary printing."""
    manager = TasksManager(tasks_file)
    manager.journal = MagicMock()

    manager.print_summary()

    manager.journal.print.assert_called()
    # Check that table was printed
    args = manager.journal.print.call_args[0]
    assert "Blondie Task Status" in args[0].title


def test_save_tasks(tmp_path):
    """Test saving tasks back to file."""
    f = tmp_path / "TASKS.md"
    f.write_text("# H\n## Todo\n- [ ] 001 | P1 | T1", encoding="utf-8")
    manager = TasksManager(f)

    # Add a new task programmatically to check if it's saved
    new_task = Task(
        id="002", title="T2", status=TaskStatus.TODO, priority="P2", depends_on=[], raw_line="", project_id="B"
    )
    manager.tasks.append(new_task)

    # pylint: disable-next=protected-access
    manager._save()

    content = f.read_text("utf-8")
    assert "001" in content
    assert "002" in content
    assert "T2" in content
