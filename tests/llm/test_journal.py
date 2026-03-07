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
    assert calls[0].args[0] == "Level 0"

    # Indented print is split into two calls
    assert calls[1].args[0] == "│   "
    assert calls[1].kwargs.get("end") == ""
    assert calls[2].args[0] == "Level 1"

    assert calls[3].args[0] == "Level 0"


def test_journal_span(tmp_path):
    """Test journal span context manager."""
    journal = Journal(root_dir=tmp_path)
    journal.console = MagicMock()

    with journal.span("My Span"):
        journal.print("Inside")

    assert journal.indent_level == 0
    # Verify calls include span start/end and indented content
    calls = journal.console.print.call_args_list
    printed_args = [c.args[0] for c in calls]

    assert "╭── My Span" in printed_args
    assert "╰── My Span" in printed_args

    # Check that "Inside" is printed and preceded by indentation
    assert "Inside" in printed_args
    idx = printed_args.index("Inside")
    assert idx > 0
    assert printed_args[idx - 1] == "│   "


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
