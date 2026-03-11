# tests/lib/test_setup_repo.py

"""Unit tests for setup_repo module."""

from unittest.mock import patch

from lib.setup_repo import setup_temp_repo


def test_setup_temp_repo(tmp_path):
    """Test setting up a temporary repo structure."""
    repo = tmp_path / "repo"
    remote = tmp_path / "remote.git"
    config = tmp_path / ".agent"
    config.mkdir()
    (config / "llm.yaml").touch()

    # Mock subprocess run to avoid actual git commands but verify flow
    with patch("subprocess.run") as mock_run:
        setup_temp_repo(repo, remote, agent_config_path=config)

        assert repo.exists()
        assert remote.exists()
        assert (repo / "README.md").exists()
        assert (repo / ".gitignore").exists()
        assert (repo / ".agent").exists()

        assert mock_run.call_count > 5


def test_setup_temp_repo_cleanup(tmp_path):
    """Test cleanup of existing directories."""
    repo = tmp_path / "repo"
    remote = tmp_path / "remote.git"
    repo.mkdir()
    remote.mkdir()

    with patch("subprocess.run"), patch("shutil.rmtree") as mock_rm:
        setup_temp_repo(repo, remote)

        assert mock_rm.call_count == 2
