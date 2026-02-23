# src/agent/project.py

"""Project configuration parser."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel


class Project(BaseModel):
    """Parsed project.yaml configuration."""

    id: str
    name: str | None = None
    languages: list[str] = []
    main_branch: str = "main"
    task_source: str = "TASKS.md"
    commands: dict[str, str] = {}
    policy: str = "POLICY.yaml"
    docs: list[str] = []
    deploy: dict[str, str] = {}
    mode: Literal["once", "continuous"] = "continuous"

    @classmethod
    def from_file(cls, path: Path) -> Project:
        """Parse project.yaml."""
        if not path.exists():
            raise FileNotFoundError(f"Project config not found at {path}")

        content = path.read_text(encoding="utf-8")
        data = yaml.safe_load(content) or {}
        return cls(**data)
