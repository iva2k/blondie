# src/lib/shell_cmd_policy.py

"""Shell command policy checker."""

from __future__ import annotations

from typing import TYPE_CHECKING

from lib.shell_cmd_parser import ShellCommandParser

if TYPE_CHECKING:
    from agent.interaction import InteractionProvider
    from agent.policy import Policy
    from llm.journal import Journal


class ShellCommandPolicy:
    """Parses and checks shell commands against agent policy."""

    def __init__(self, policy: Policy, journal: Journal, interactor: InteractionProvider):
        self.policy = policy
        self.journal = journal
        self.interactor = interactor

    def check(self, command_str: str, default_gate: str | None = None) -> tuple[bool, str | None]:
        """
        Checks a command string against the policy.
        Returns (is_allowed, reason). `reason` is an error message if not allowed.
        """
        if default_gate:
            allowed, reason = self._check_gate(default_gate)
            if not allowed:
                return False, reason

        command_parts = ShellCommandParser.split_commands(command_str)
        for part in command_parts:
            gate = ShellCommandParser.detect_gate(part)
            if gate:
                allowed, reason = self._check_gate(gate)
                if not allowed:
                    if gate == "shell-files":
                        return False, "BLOCKED (use tool calls and plan actions to generate code)"
                    return False, reason

        return True, None

    def _check_gate(self, action: str) -> tuple[bool, str | None]:
        """
        Checks a specific action/gate against the policy.
        Returns (is_allowed, reason).
        """
        permission = self.policy.check_permission(action)
        if permission == "allow":
            return True, None
        if permission == "forbid":
            self.journal.print(f"⛔ Action '{action}' forbidden by POLICY.yaml")
            reason = "SKIPPED_BY_POLICY"
            hint = ""
            if action == "shell-files":
                hint = "use tool calls and plan actions to generate code"
            # Add more action hints here, convert to dict lookup.
            if hint:
                reason += f" ({hint})"
            return False, reason

        # prompt
        if self.interactor.prompt_user(f"❓ Action '{action}' requires approval (POLICY.yaml)"):
            return True, None

        return False, "SKIPPED_BY_USER"
