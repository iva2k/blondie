# tests/llm/test_journal.py

"""Unit tests for Journal logging."""

from unittest.mock import MagicMock

from llm.journal import Journal


def test_journal_indentation(tmp_path):
    """Test journal indentation logic."""
    journal = Journal(root_dir=tmp_path)
    journal.console = MagicMock()

    journal.print("Level 0")
    journal.indent()
    journal.print("Level 1")
    journal.dedent()
    journal.print("Level 0")

    # Check console calls
    calls = journal.console.print.call_args_list
    assert calls[0][0][0] == "Level 0"
    assert calls[1][0] == ("│   ", "Level 1")
    assert calls[2][0][0] == "Level 0"


def test_journal_span(tmp_path):
    """Test journal span context manager."""
    journal = Journal(root_dir=tmp_path)
    journal.console = MagicMock()

    with journal.span("My Span"):
        journal.print("Inside")

    assert journal.indent_level == 0
    # Verify calls include span start/end and indented content
    calls = [c[0] for c in journal.console.print.call_args_list]
    # Flatten args
    flat_calls = []
    for args in calls:
        flat_calls.append("".join(str(a) for a in args))

    assert any("╭── My Span" in c for c in flat_calls)
    assert any("│   Inside" in c for c in flat_calls)
    assert any("╰── My Span" in c for c in flat_calls)


def test_journal_json_indentation(tmp_path):
    """Test that JSON logs are indented."""
    journal = Journal(root_dir=tmp_path)
    journal.start_task("test-task")

    journal.indent()
    journal.log_shell("echo hi", 0, "hi", "")

    log_file = journal.current_log_file
    assert log_file is not None
    content = log_file.read_text(encoding="utf-8")

    # Check for indented JSON lines
    # The log_shell writes:
    # \n│   === SHELL ... ===\n
    # │   {
    # │     "type": "SHELL",
    # ...
    assert "\n│   {" in content
    assert '\n│     "command": "echo hi",' in content
