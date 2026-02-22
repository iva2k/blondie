# src/agent/policy.py

"""Policy parser for Blondie agent."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel


class AutonomyRule(BaseModel):
    """Single autonomy rule mapping action to permission level."""

    action: str
    permission: Literal["allow", "prompt", "forbid"]


class Policy(BaseModel):
    """Parsed POLICY.yaml configuration for repo autonomy and commands."""

    gates: dict[str, Literal["allow", "prompt", "forbid"]] = {}
    autonomy: dict[str, Any] = {}
    limits: dict[str, Any] = {}
    commands: dict[str, str] = {}
    git_strategy: dict[str, str] = {}
    docs: list[str] = []

    @classmethod
    def from_file(cls, path: Path) -> Policy:
        """Parse POLICY.yaml."""
        content = path.read_text(encoding="utf-8")
        data = yaml.safe_load(content) or {}

        # Flatten autonomy.gates -> gates
        if "autonomy" in data and isinstance(data["autonomy"], dict):
            data["gates"] = data["autonomy"].get("gates", {})

        return cls(**data)

    def check_permission(self, action: str) -> Literal["allow", "prompt", "forbid"]:
        """Check permission for specific action with prefix matching."""
        # Exact match first
        if action in self.gates:
            return self.gates[action]

        # Prefix wildcard matching (deploy-*)
        for pattern, permission in self.gates.items():
            if pattern.endswith("*") and action.startswith(pattern[:-1]):
                return permission

        # Default: fully autonomous
        return "allow"

    def get_command(self, command: str) -> str | None:
        """Get command template for named operation."""
        return self.commands.get(command)


if __name__ == "__main__":
    policy = Policy.from_file(Path(".agent/POLICY.yaml"))
    print(f"git-merge: {policy.check_permission('git-merge')}")
    print(f"deploy-prod: {policy.check_permission('deploy-prod')}")
