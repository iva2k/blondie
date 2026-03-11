# tests/agent/test_progress.py

"""Unit tests for ProgressManager."""

from agent.progress import ProgressManager


def test_add_action(tmp_path):
    """Test adding an action log entry."""
    p_file = tmp_path / "progress.txt"
    pm = ProgressManager(p_file)
    pm.add_action("TEST", "details", "STATUS")

    assert p_file.exists()
    content = p_file.read_text("utf-8")
    assert "TEST: details (STATUS)" in content
    assert "[" in content and "]" in content  # Timestamp check


def test_read_empty(tmp_path):
    """Test reading from a non-existent file returns empty string."""
    pm = ProgressManager(tmp_path / "nonexistent.txt")
    assert pm.read() == ""


def test_clear(tmp_path):
    """Test clearing the progress file."""
    p_file = tmp_path / "progress.txt"
    p_file.write_text("content", "utf-8")
    pm = ProgressManager(p_file)
    pm.clear()
    assert p_file.read_text("utf-8") == ""


def test_archive(tmp_path):
    """Test archiving the progress file."""
    p_file = tmp_path / "progress.txt"
    p_file.write_text("content", "utf-8")
    pm = ProgressManager(p_file)

    dest_dir = tmp_path / "archive"
    pm.archive(dest_dir)

    assert (dest_dir / "progress.txt").exists()
    assert (dest_dir / "progress.txt").read_text("utf-8") == "content"


def test_add_llm_event(tmp_path):
    """Test logging an LLM event."""
    pm = ProgressManager(tmp_path / "progress.txt")
    pm.add_llm_event("EVENT", "skill", "op", "provider", "model", "STATUS")

    content = pm.read()
    assert "EVENT: Skill: skill | Op: op | provider/model (STATUS)" in content
