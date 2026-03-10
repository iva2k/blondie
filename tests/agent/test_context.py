# tests/agent/test_context.py

"""Unit tests for ContextGatherer."""

import os
from unittest.mock import MagicMock, patch

import pytest

from agent.context import ContextGatherer
from agent.tasks import Task, TaskStatus
from lib.gitignore import GitIgnore


@pytest.fixture
def mock_deps(tmp_path):
    """Create mock dependencies."""
    repo_path = tmp_path / "repo"
    repo_path.mkdir()

    # Create some files
    (repo_path / "file.txt").write_text("content", encoding="utf-8")
    (repo_path / "ignored.txt").write_text("ignored", encoding="utf-8")
    (repo_path / ".git").mkdir()

    project = MagicMock()
    project.model_dump.return_value = {"id": "test"}
    project.protected_files = ["protected.txt"]
    project.dev_env = {"guidelines": ["Be nice"]}

    policy = MagicMock()
    policy.model_dump.return_value = {"gates": {}}

    git = MagicMock()
    git.current_branch.return_value = "main"
    git.status.return_value = "clean"

    gitignore = MagicMock()
    # Mock is_ignored: True if filename contains "ignored"
    gitignore.is_ignored.side_effect = lambda p: "ignored" in str(p)

    progress = MagicMock()
    progress.read.return_value = "Step 1 done"

    return {
        "repo_path": repo_path,
        "project": project,
        "policy": policy,
        "git": git,
        "gitignore": gitignore,
        "progress": progress,
    }


@pytest.fixture
def context_gatherer(mock_deps):
    """Create ContextGatherer instance."""
    return ContextGatherer(
        mock_deps["repo_path"],
        mock_deps["project"],
        mock_deps["policy"],
        mock_deps["git"],
        mock_deps["gitignore"],
        mock_deps["progress"],
    )


def test_gather_all(context_gatherer):
    """Test gathering all context sections."""
    # Setup task
    task = Task(
        id="001",
        title="Test Task",
        status=TaskStatus.TODO,
        priority="P0",
        depends_on=[],
        raw_line="",
        project_id="TEST",
    )
    context_gatherer.add_task(task)
    context_gatherer.add_command("ls -la")

    # Request all sections
    items = {
        "cwd": True,
        "project": True,
        "policy": True,
        "git": True,
        "files": True,
        "task": True,
        "command": True,
        "progress": True,
        "env": True,
        "os": True,
    }

    full_text, parts = context_gatherer.gather(items)

    # Check text output
    assert "## CONTEXT GUIDE\n\n" in full_text
    assert "## CONTEXT\n\n" in full_text
    assert "- `[OS]`: The current operating system environment." in full_text
    assert "- `[ARCH]`: " in full_text
    assert "- `[SHELL]`: " in full_text
    assert "### [CWD]" in full_text
    assert "### [PROJECT]" in full_text
    assert "### [GIT]" in full_text
    assert "### [FILES]" in full_text
    assert "### [TASK]" in full_text
    assert "### [COMMAND]" in full_text
    assert "### [PROGRESS]" in full_text
    assert "### [ENV]" in full_text
    assert "### [OS]" in full_text

    # Check specific content
    assert "file.txt" in parts["files"]
    assert "ignored.txt" not in parts["files"]
    assert "ls -la" in parts["command"]
    assert "Test Task" in parts["task"]
    assert "Be nice" in parts["env"]


def test_file_tree_protected(context_gatherer, mock_deps):
    """Test file tree marks protected files."""
    (mock_deps["repo_path"] / "protected.txt").write_text("secret", encoding="utf-8")

    _, parts = context_gatherer.gather({"files": True})

    assert "protected.txt (* protected)" in parts["files"]


def test_os_context(context_gatherer):
    """Test OS context gathering."""
    with (
        patch("platform.system", return_value="Linux"),
        patch("platform.release", return_value="5.4.0"),
        patch.dict(os.environ, {"SHELL": "/bin/bash"}),
    ):
        _, parts = context_gatherer.gather({"os": True})

        assert "Linux" in parts["os"]
        assert "/bin/bash" in parts["shell"]


def test_refresh(context_gatherer):
    """Test refresh method (currently no-op but should exist)."""
    context_gatherer.refresh()


def test_env_context(context_gatherer, mock_deps):
    """Test environment context gathering."""
    mock_deps["project"].dev_env = {"guidelines": ["Rule 1", "Rule 2"]}

    _, parts = context_gatherer.gather({"env": True})

    assert "Rule 1" in parts["env"]
    assert "Rule 2" in parts["env"]


def test_gather_user_args(context_gatherer):
    """Test gathering context with user arguments."""
    full_text, _ = context_gatherer.gather({}, user_args=["task_title", "unknown_arg"])

    assert "You are also provided with these inputs in the user prompt:" in full_text
    assert "- `[TASK_TITLE]`: The title of the task to be performed." in full_text
    assert "- `[UNKNOWN_ARG]`: User input: unknown arg" in full_text


def test_get_files_context_with_gitignore(mock_deps):
    """Test that _get_files_context correctly filters based on a real .gitignore file."""
    repo_path = mock_deps["repo_path"]
    # Create a .gitignore file
    (repo_path / ".gitignore").write_text("*.log\nbuild/\n", encoding="utf-8")

    # Create files and directories to be tested
    (repo_path / "app.py").write_text("print('hello')", encoding="utf-8")
    (repo_path / "error.log").write_text("error", encoding="utf-8")
    build_dir = repo_path / "build"
    build_dir.mkdir()
    (build_dir / "output.bin").write_text("binary", encoding="utf-8")
    (repo_path / ".dotfile").write_text("hidden", encoding="utf-8")

    # Use the real GitIgnore class, not the mock
    gitignore = GitIgnore(repo_path)
    gatherer = ContextGatherer(
        repo_path,
        mock_deps["project"],
        mock_deps["policy"],
        mock_deps["git"],
        gitignore,
        mock_deps["progress"],
    )

    # pylint: disable-next=protected-access
    files_context = gatherer._get_files_context()

    assert isinstance(files_context, str)
    assert "app.py" in files_context
    assert "error.log" not in files_context
    assert "build/output.bin" not in files_context
    assert ".gitignore" in files_context  # .gitignore itself is not ignored
    assert ".dotfile" not in files_context  # Ignored by the `part.startswith(".")` logic
