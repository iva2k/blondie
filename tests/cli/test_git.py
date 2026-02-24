# tests/cli/test_git.py

"""Unit tests for Git CLI wrapper."""

from unittest.mock import MagicMock, patch

import pytest

from agent.executor import CommandResult
from agent.policy import Policy
from cli.git import GitCLI
from llm.journal import Journal


@pytest.fixture
def mock_policy():
    """Create a mock policy allowing everything by default."""
    policy = MagicMock(spec=Policy)
    policy.check_permission.return_value = "allow"
    return policy


@pytest.fixture
def git_cli(mock_policy, tmp_path):
    """Create GitCLI instance with mock policy."""
    return GitCLI(tmp_path, mock_policy, Journal())


def test_run_allow(git_cli, mock_policy):
    """Test allowed git command execution."""
    git_cli.executor.run = MagicMock(return_value=CommandResult("git status", 0, "", ""))

    git_cli.run("status")

    git_cli.executor.run.assert_called_once()
    args, kwargs = git_cli.executor.run.call_args
    assert "git" in args[0] and "status" in args[0]
    assert kwargs["gate"] == "git-status"


def test_run_forbid(git_cli, mock_policy):
    """Test forbidden git command raises error."""
    mock_policy.check_permission.return_value = "forbid"

    # Simulate Executor returning policy block
    git_cli.executor.run = MagicMock(return_value=CommandResult("git push", 125, "", "SKIPPED_BY_POLICY"))

    with pytest.raises(PermissionError, match="forbidden by POLICY.yaml"):
        git_cli.run("push")


def test_run_prompt_approve(git_cli, mock_policy):
    """Test prompt approval flow."""
    # GitCLI delegates to Executor. If Executor approves/runs, it returns success.
    git_cli.executor.run = MagicMock(return_value=CommandResult("git merge", 0, "", ""))

    git_cli.run("merge")
    git_cli.executor.run.assert_called_once()


def test_run_prompt_deny(git_cli, mock_policy):
    """Test prompt denial flow."""
    # If Executor denies, it returns SKIPPED_BY_POLICY
    git_cli.executor.run = MagicMock(return_value=CommandResult("git merge", 125, "", "SKIPPED_BY_POLICY"))

    with pytest.raises(PermissionError, match="forbidden by POLICY.yaml"):
        git_cli.run("merge")


def test_current_branch(git_cli):
    """Test getting current branch."""
    git_cli.executor.run = MagicMock(return_value=CommandResult("git branch", 0, "main\n", ""))
    branch = git_cli.current_branch()
    assert branch == "main"


def test_is_clean(git_cli):
    """Test clean status check."""
    git_cli.executor.run = MagicMock()

    # Case 1: Clean (exit 0)
    git_cli.executor.run.return_value = CommandResult("git diff", 0, "", "")
    assert git_cli.is_clean() is True

    # Case 2: Dirty (exit 1)
    git_cli.executor.run.return_value = CommandResult("git diff", 1, "", "")
    assert git_cli.is_clean() is False


def test_create_pr_branch_switch(git_cli):
    """Test creating PR branch when we need to switch and commit."""
    with (
        patch.object(git_cli, "current_branch", return_value="main"),
        patch.object(git_cli, "checkout_branch") as mock_checkout,
        patch.object(git_cli, "status", return_value=" M file.txt"),
        patch.object(git_cli, "add_all") as mock_add,
        patch.object(git_cli, "commit") as mock_commit,
        patch.object(git_cli, "push") as mock_push,
    ):
        git_cli.create_pr_branch("123")

        mock_checkout.assert_called_with("task-123")
        mock_add.assert_called_once()
        mock_commit.assert_called_with("task 123")
        mock_push.assert_called_with("task-123")


def test_create_pr_branch_already_on_branch_clean(git_cli):
    """Test creating PR branch when already on branch and clean."""
    with (
        patch.object(git_cli, "current_branch", return_value="task-123"),
        patch.object(git_cli, "checkout_branch") as mock_checkout,
        patch.object(git_cli, "status", return_value=""),
    ):
        git_cli.create_pr_branch("123")

        mock_checkout.assert_not_called()
