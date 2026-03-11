# tests/agent/test_interaction.py

"""Unit tests for Interaction module."""

from unittest.mock import MagicMock

from agent.interaction import ConsoleInteractionProvider


def test_console_prompt_yes():
    """Test user approval."""
    journal = MagicMock()
    journal.console.input.return_value = "y"
    provider = ConsoleInteractionProvider(journal)
    assert provider.prompt_user("msg") is True
    journal.print.assert_any_call("msg")


def test_console_prompt_no():
    """Test user denial."""
    journal = MagicMock()
    journal.console.input.return_value = "n"
    provider = ConsoleInteractionProvider(journal)
    assert provider.prompt_user("msg") is False
    journal.print.assert_any_call("⏭️  Skipping command.")
