# tests/cli/test_git.py

"""Unit tests for Git CLI wrapper."""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

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
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(args=["git", "status"], returncode=0, stdout="", stderr="")

        git_cli.run("status")

        mock_run.assert_called_once()
        args, _ = mock_run.call_args
        assert args[0] == ["git", "status"]


def test_run_forbid(git_cli, mock_policy):
    """Test forbidden git command raises error."""
    mock_policy.check_permission.return_value = "forbid"

    with pytest.raises(PermissionError, match="forbidden by POLICY.yaml"):
        git_cli.run("push")


def test_run_prompt_approve(git_cli, mock_policy):
    """Test prompt approval flow."""
    mock_policy.check_permission.return_value = "prompt"
    git_cli.journal.console.input = MagicMock(return_value="y")

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(args=["git", "merge"], returncode=0, stdout="", stderr="")
        git_cli.run("merge")
        mock_run.assert_called_once()


def test_run_prompt_deny(git_cli, mock_policy):
    """Test prompt denial flow."""
    mock_policy.check_permission.return_value = "prompt"
    git_cli.journal.console.input = MagicMock(return_value="n")

    with pytest.raises(PermissionError):
        git_cli.run("merge")


def test_current_branch(git_cli):
    """Test getting current branch."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(
            args=["git", "branch"], returncode=0, stdout="main\n", stderr=""
        )
        branch = git_cli.current_branch()
        assert branch == "main"


def test_is_clean(git_cli):
    """Test clean status check."""
    with patch("subprocess.run") as mock_run:
        # Case 1: Clean (exit 0)
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        assert git_cli.is_clean() is True

        # Case 2: Dirty (exit 1)
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="")
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


def test_configure_author(tmp_path, mock_policy):
    """Test that git author configuration runs git config commands."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        GitCLI(tmp_path, mock_policy, Journal(), user="Bot", email="bot@test.com")

        assert mock_run.call_count == 2
        calls = mock_run.call_args_list
        args1, _ = calls[0]
        args2, _ = calls[1]
        assert args1[0] == ["git", "config", "user.name", "Bot"]
        assert args2[0] == ["git", "config", "user.email", "bot@test.com"]
