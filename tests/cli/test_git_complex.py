# tests/cli/test_git_complex.py

"""Complex unit tests for Git CLI wrapper."""

import subprocess
from unittest.mock import MagicMock, call, patch

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


def test_merge_if_clean_with_exclusions(git_cli):
    """Test merge_if_clean with the exclude_files argument."""
    with patch.object(git_cli, "is_clean", return_value=True):
        with patch.object(git_cli, "run") as mock_run:
            # Mock the sequence of git commands
            # The final commit call is what we're most interested in.
            # We need to ensure the checkout/rm happens before it.
            # We'll mock the returncode for the checkout to simulate the file existing in HEAD.
            def run_side_effect(*args, **_kwargs):
                if args[0] == "checkout" and args[1] == "HEAD":
                    return MagicMock(returncode=0)
                return MagicMock()

            mock_run.side_effect = run_side_effect

            result = git_cli.merge_if_clean("feature-branch", "main", exclude_files=["progress.txt"])

            assert result is True

            # Verify the sequence of calls
            expected_calls = [
                call("checkout", "main"),
                call("pull", "origin", "main"),
                call("merge", "--no-ff", "--no-commit", "feature-branch"),
                call("checkout", "HEAD", "--", "progress.txt", check=False),
                call("commit", "--no-edit"),
                call("push", "origin", "main"),
            ]
            mock_run.assert_has_calls(expected_calls, any_order=False)


def test_merge_if_clean_with_exclusions_file_not_in_head(git_cli):
    """Test merge_if_clean where excluded file is new and not in HEAD."""
    with patch.object(git_cli, "is_clean", return_value=True):
        with patch.object(git_cli, "run") as mock_run:
            # Mock the sequence of git commands
            # This time, checkout HEAD fails (returncode != 0)
            def run_side_effect(*args, **_kwargs):
                if args[0] == "checkout" and args[1] == "HEAD":
                    return MagicMock(returncode=1)  # File not in HEAD
                return MagicMock()

            mock_run.side_effect = run_side_effect
            (git_cli.repo_path / "progress.txt").touch()  # Make file exist for unlink check

            result = git_cli.merge_if_clean("feature-branch", "main", exclude_files=["progress.txt"])

            assert result is True

            # Verify the sequence of calls
            expected_calls = [
                call("checkout", "main"),
                call("pull", "origin", "main"),
                call("merge", "--no-ff", "--no-commit", "feature-branch"),
                call("checkout", "HEAD", "--", "progress.txt", check=False),
                call("rm", "--cached", "-f", "progress.txt", check=False),  # This should be called now
                call("commit", "--no-edit"),
                call("push", "origin", "main"),
            ]
            mock_run.assert_has_calls(expected_calls, any_order=False)
            assert not (git_cli.repo_path / "progress.txt").exists()  # Check it was unlinked


def test_merge_if_clean_merge_conflict(git_cli):
    """Test that merge fails and aborts on a conflict."""
    with patch.object(git_cli, "is_clean", return_value=True):
        with patch.object(git_cli, "run") as mock_run:
            # Simulate a CalledProcessError on the merge command
            mock_run.side_effect = [
                MagicMock(),  # checkout
                MagicMock(),  # pull
                subprocess.CalledProcessError(1, "git merge"),  # merge fails
                MagicMock(),  # merge --abort
            ]

            result = git_cli.merge_if_clean("feature", "main")
            assert result is False

            # Verify that merge --abort was called
            mock_run.assert_any_call("merge", "--abort", check=False)
