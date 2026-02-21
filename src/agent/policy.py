"""Policy parser for Blondie agent."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel


class AutonomyRule(BaseModel):
    """Single autonomy rule mapping action to permission level."""

    action: str
    permission: Literal["allow", "prompt", "forbid"]


class Policy(BaseModel):
    """Parsed POLICY.md configuration for repo autonomy and commands."""

    gates: dict[str, str] = {}
    commands: dict[str, str] = {}
    git_strategy: dict[str, str] = {}
    docs: list[str] = []

    @classmethod
    def from_file(cls, path: Path) -> Policy:
        """Parse POLICY.md using YAML frontmatter or markdown sections."""
        content = path.read_text(encoding="utf-8")

        # Extract YAML frontmatter
        yaml_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
        if yaml_match:
            data = yaml.safe_load(yaml_match.group(1) or "{}")
        else:
            data = cls._parse_markdown_sections(content)

        return cls(**data)

    @staticmethod
    def _parse_markdown_sections(content: str) -> dict:
        """Fallback parser for plain markdown POLICY.md files."""
        gates: dict[str, str] = {}
        commands: dict[str, str] = {}

        for line in content.splitlines():
            if ": " in line and not line.strip().startswith("#"):
                key, value = line.split(": ", 1)
                key = key.strip().lower().replace("-", "_")
                value = value.strip()

                if any(gate_word in content.lower() for gate_word in ["gates", "autonomy"]):
                    if key in ["git_merge", "deploy_prod", "action"]:
                        gates[key] = value.lower()
                elif key in ["install", "test", "build", "deploy", "lint"]:
                    commands[key] = value

        return {"gates": gates, "commands": commands}

    def check_permission(self, action: str) -> Literal["allow", "prompt", "forbid"]:
        """Check permission for specific action with prefix matching."""
        # Exact match first
        if action in self.gates:
            return self.gates[action]  # type: ignore

        # Prefix wildcard matching (deploy-*)
        for pattern, permission in self.gates.items():
            if pattern.endswith("*") and action.startswith(pattern[:-1]):
                return permission  # type: ignore

        # Default: fully autonomous
        return "allow"

    def get_command(self, command: str) -> str | None:
        """Get command template for named operation."""
        return self.commands.get(command)


if __name__ == "__main__":
    policy = Policy.from_file(Path(".agent/POLICY.md"))
    print(f"git-merge: {policy.check_permission('git-merge')}")
    print(f"deploy-prod: {policy.check_permission('deploy-prod')}")
