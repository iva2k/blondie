# tests/cli/test_git.py

"""Unit tests for Git CLI wrapper."""

from unittest.mock import MagicMock, patch

import pytest

from agent.policy import Policy
from cli.git import GitCLI


@pytest.fixture
def mock_policy():
    """Create a mock policy allowing everything by default."""
    policy = MagicMock(spec=Policy)
    policy.check_permission.return_value = "allow"
    return policy


@pytest.fixture
def git_cli(mock_policy, tmp_path):
    """Create GitCLI instance with mock policy."""
    return GitCLI(tmp_path, mock_policy)


def test_run_allow(git_cli, mock_policy):
    """Test allowed git command execution."""
    with patch("subprocess.run") as mock_run:
        git_cli.run("status")

        mock_policy.check_permission.assert_called_with("git-status")
        mock_run.assert_called_once()
        args, kwargs = mock_run.call_args
        assert args[0] == ["git", "status"]
        assert kwargs["cwd"] == git_cli.repo_path


def test_run_forbid(git_cli, mock_policy):
    """Test forbidden git command raises error."""
    mock_policy.check_permission.return_value = "forbid"

    with pytest.raises(PermissionError, match="forbidden by POLICY.yaml"):
        git_cli.run("push")


def test_run_prompt_approve(git_cli, mock_policy):
    """Test prompt approval flow."""
    mock_policy.check_permission.return_value = "prompt"

    with patch("subprocess.run") as mock_run:
        # Patch the console object instance in the module
        with patch("cli.git.console.input", return_value="y"):
            git_cli.run("merge")
            mock_run.assert_called_once()


def test_run_prompt_deny(git_cli, mock_policy):
    """Test prompt denial flow."""
    mock_policy.check_permission.return_value = "prompt"

    with patch("subprocess.run") as mock_run:
        with patch("cli.git.console.input", return_value="n"):
            with pytest.raises(PermissionError, match="User denied"):
                git_cli.run("merge")
            mock_run.assert_not_called()


def test_current_branch(git_cli):
    """Test getting current branch."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.stdout = "main\n"
        branch = git_cli.current_branch()
        assert branch == "main"
        mock_run.assert_called_with(
            ["git", "branch", "--show-current"],
            cwd=git_cli.repo_path,
            capture_output=True,
            text=True,
            check=True,
        )


def test_is_clean(git_cli):
    """Test clean status check."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        assert git_cli.is_clean() is True

        mock_run.return_value.returncode = 1
        assert git_cli.is_clean() is False


def test_create_pr_branch_switch(git_cli):
    """Test creating PR branch when we need to switch and commit."""
    with patch.object(git_cli, "current_branch", return_value="main"), \
         patch.object(git_cli, "checkout_branch") as mock_checkout, \
         patch.object(git_cli, "status", return_value=" M file.txt"), \
         patch.object(git_cli, "add_all") as mock_add, \
         patch.object(git_cli, "commit") as mock_commit, \
         patch.object(git_cli, "push") as mock_push:

        git_cli.create_pr_branch("123")

        mock_checkout.assert_called_with("task-123")
        mock_add.assert_called_once()
        mock_commit.assert_called_with("task 123")
        mock_push.assert_called_with("task-123")


def test_create_pr_branch_already_on_branch_clean(git_cli):
    """Test creating PR branch when already on branch and clean."""
    with patch.object(git_cli, "current_branch", return_value="task-123"), \
         patch.object(git_cli, "checkout_branch") as mock_checkout, \
         patch.object(git_cli, "status", return_value=""):

        git_cli.create_pr_branch("123")

        mock_checkout.assert_not_called()
