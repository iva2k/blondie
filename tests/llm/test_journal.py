# tests/llm/test_journal.py

"""Unit tests for Journal logging."""

from unittest.mock import MagicMock, patch

from llm.client import LLMResponse
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


def test_log_chat_to_file(tmp_path):
    """Test logging chat interaction to file."""
    journal = Journal(root_dir=tmp_path)
    journal.start_task("test-chat")

    response = LLMResponse(content="Response", model="gpt-4", tokens_used=10, cost_usd=0.01, tool_calls=[])

    journal.log_chat("op", "provider", "User Prompt", response, title="Chat Title")

    log_file = journal.current_log_file
    assert log_file is not None
    assert log_file.exists()
    content = log_file.read_text(encoding="utf-8")
    assert "LLM CHAT (op)" in content
    assert "User Prompt" in content
    assert "Response" in content
    assert "Chat Title" in content


def test_write_raw_exception(tmp_path):
    """Test handling of write exceptions."""
    journal = Journal(root_dir=tmp_path)
    journal.start_task("test-error")
    journal.console = MagicMock()

    # Simulate IO Error
    with patch("builtins.open", side_effect=OSError("Disk failure")):
        journal.write_raw("Should fail")

    journal.console.print.assert_called_once()
    args, _ = journal.console.print.call_args
    assert "Journal write failed" in args[0]
    assert "Disk failure" in args[0]


def test_print_truncate(tmp_path):
    """Test that print truncates long messages."""
    journal = Journal(root_dir=tmp_path)
    journal.console = MagicMock()
    journal.print("a" * 100, truncate=50)
    args, _ = journal.console.print.call_args
    assert len(args[0]) < 70
    assert "..." in args[0]
    assert "[truncated]" in args[0]


def test_start_task_no_root_dir():
    """Test start_task does nothing if root_dir is not set."""
    journal = Journal()
    journal.start_task("test")
    assert journal.current_log_file is None


def test_log_shell_branches(tmp_path):
    """Test all branches of log_shell."""
    journal = Journal(root_dir=tmp_path)
    journal.start_task("test")
    journal.console = MagicMock()

    # Success
    journal.log_shell("cmd1", 0, "out", "err", 1.0)
    journal.console.print.assert_any_call("✅ command ok (1.00s)")

    # Timeout
    journal.log_shell("cmd2", 124, "out", "Timeout", 1.0)
    journal.console.print.assert_any_call("⏱️ command Timeout (1.00s)")

    # Expected error
    journal.log_shell("cmd3", 1, "out", "err", 1.0, expect_error=True)
    journal.console.print.assert_any_call("❌ command failed normally (was expected) (exit 1) Error: err (1.00s)")

    # Unexpected error
    journal.log_shell("cmd4", 1, "out", "err", 1.0, expect_error=False)
    journal.console.print.assert_any_call("❌ command failed (exit 1) Error: err (1.00s)")


def test_log_chat_string_response(tmp_path):
    """Test log_chat with a simple string response."""
    journal = Journal(root_dir=tmp_path)
    journal.start_task("test")
    journal.log_chat("op", "provider", "prompt", "just a string")
    assert journal.current_log_file is not None
    content = journal.current_log_file.read_text()
    assert '"content": "just a string"' in content
