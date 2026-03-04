# src/agent/interaction.py

"""User interaction providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from llm.journal import Journal


class InteractionProvider(ABC):
    """Abstract base class for handling user interaction prompts."""

    @abstractmethod
    def prompt_user(self, message: str) -> bool:
        """Prompt the user for a yes/no decision."""


class ConsoleInteractionProvider(InteractionProvider):
    """Interaction provider that uses the console for user prompts."""

    def __init__(self, journal: Journal):
        self.journal = journal

    def prompt_user(self, message: str) -> bool:
        """Prompt the user via the console."""
        self.journal.print(message)
        answer = self.journal.console.input("[Approve? (y/N)] ").strip().lower()
        if not answer.startswith("y"):
            self.journal.print("⏭️  Skipping command.")
            return False
        return True
