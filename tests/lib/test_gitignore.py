# tests/lib/test_gitignore.py

"""Unit tests for GitIgnore module."""

from lib.gitignore import GitIgnore


def test_ignore_simple(tmp_path):
    """Test simple extensions and directories."""
    (tmp_path / ".gitignore").write_text("*.log\nnode_modules/", encoding="utf-8")
    gi = GitIgnore(tmp_path)

    assert gi.is_ignored(tmp_path / "test.log")
    assert gi.is_ignored(tmp_path / "node_modules" / "pkg.json")
    assert not gi.is_ignored(tmp_path / "test.txt")


def test_ignore_negation(tmp_path):
    """Test negation patterns."""
    (tmp_path / ".gitignore").write_text("*.log\n!important.log", encoding="utf-8")
    gi = GitIgnore(tmp_path)

    assert gi.is_ignored(tmp_path / "other.log")
    assert not gi.is_ignored(tmp_path / "important.log")


def test_ignore_nested(tmp_path):
    """Test nested directory ignoring."""
    (tmp_path / ".gitignore").write_text("build/", encoding="utf-8")
    gi = GitIgnore(tmp_path)

    assert gi.is_ignored(tmp_path / "build" / "output.txt")
    assert gi.is_ignored(tmp_path / "src" / "build" / "output.txt")


def test_no_gitignore_file(tmp_path):
    """Test behavior when .gitignore is missing."""
    gi = GitIgnore(tmp_path)
    # .git is always ignored
    assert gi.is_ignored(tmp_path / ".git" / "HEAD")
    assert not gi.is_ignored(tmp_path / "file.txt")


def test_slash_prefix(tmp_path):
    """Test root-only patterns."""
    (tmp_path / ".gitignore").write_text("/rootonly.txt", encoding="utf-8")
    gi = GitIgnore(tmp_path)

    assert gi.is_ignored(tmp_path / "rootonly.txt")
    assert not gi.is_ignored(tmp_path / "subdir" / "rootonly.txt")
