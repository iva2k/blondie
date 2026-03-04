# src/lib/shell_cmd_parser.py

"""Shell command parsing and classification."""

import re


class ShellCommandParser:
    """Parses shell commands to detect actions."""

    @staticmethod
    def split_commands(command_str: str) -> list[str]:
        """
        Splits a complex shell command string into a list of simple commands.
        NOTE: This is a simplistic implementation and does not handle complex shell grammar
        like subshells, for loops with command substitution, or quoted strings containing separators.
        """
        commands = re.split(r"\s*(&&|\|\||;|\|)\s*", command_str)
        return [cmd.strip() for cmd in commands if cmd and cmd.strip() not in ("&&", "||", ";", "|")]

    @staticmethod
    def detect_gate(command_part: str) -> str | None:
        """Detects the policy gate for a given simple command part."""
        cmd_tokens = command_part.strip().split()
        if not cmd_tokens:
            return None

        idx = 0
        if cmd_tokens[0] == "sudo" and len(cmd_tokens) > 1:
            idx = 1

        main_cmd = cmd_tokens[idx]

        # Gate for file writes using echo/printf/cat
        if main_cmd in ["echo", "printf", "cat"]:
            if ">" in command_part:  # TODO: (now) pipe to tee should also be checked
                return "shell-files"

        if main_cmd == "tee" or re.search(r"\|\s*(?:sudo\s+)?tee\b", command_part, re.IGNORECASE):
            return "shell-files"

        # Heuristic for package management commands
        package_managers = ["npm", "pip", "poetry", "apt-get", "yum", "dnf", "apt", "pnpm", "yarn"]
        if main_cmd in package_managers:
            if len(cmd_tokens) > idx + 1 and cmd_tokens[idx + 1] in ["install", "add", "update", "upgrade"]:
                return "add-package"

        # Heuristic for git commands
        if main_cmd == "git" and len(cmd_tokens) > idx + 1:
            git_subcommand = cmd_tokens[idx + 1]
            if git_subcommand == "merge":
                return "git-merge"
            if git_subcommand == "push":
                return "git-push"

        return None
