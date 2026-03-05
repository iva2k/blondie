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
    """Parsed POLICY.yaml configuration for agent autonomy."""

    autonomy: dict[str, Any] = {}
    limits: dict[str, Any] = {}
    git_strategy: dict[str, str] = {}
    docs: dict[str, list[str]] = {}

    @classmethod
    def from_file(cls, path: Path) -> Policy:
        """Parse POLICY.yaml."""
        content = path.read_text(encoding="utf-8")
        data = yaml.safe_load(content) or {}

        return cls(**data)

    def check_permission(self, action: str) -> Literal["allow", "prompt", "forbid"]:
        """Check permission for specific action with prefix matching."""
        gates = self.autonomy.get("gates", {})

        # Exact match first
        if action in gates:
            return gates[action]

        # Prefix wildcard matching (deploy-*)
        for pattern, permission in gates.items():
            if pattern.endswith("*") and action.startswith(pattern[:-1]):
                return permission

        # Default: fully autonomous
        return "allow"


if __name__ == "__main__":
    policy = Policy.from_file(Path(".agent/POLICY.yaml"))
    print(f"git-merge: {policy.check_permission('git-merge')}")
    print(f"deploy-prod: {policy.check_permission('deploy-prod')}")
