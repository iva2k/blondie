# src/agent/project.py

"""Project configuration parser."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

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
    protected_files: list[str] = []
    dev_config: str = "dev.yaml"
    dev_overrides: dict[str, Any] = {}
    dev_env: dict[str, Any] = {}

    @classmethod
    def from_file(cls, path: Path) -> Project:
        """Parse project.yaml."""
        if not path.exists():
            raise FileNotFoundError(f"Project config not found at {path}")

        content = path.read_text(encoding="utf-8")
        data = yaml.safe_load(content) or {}
        project = cls(**data)

        # Load dev config
        dev_path = path.parent / project.dev_config
        if dev_path.is_file():
            try:
                dev_content = dev_path.read_text(encoding="utf-8")
                loaded_env = yaml.safe_load(dev_content) or {}
                loaded_env.update(project.dev_env)
                project.dev_env = loaded_env
            except Exception as _e:
                # TODO: (now) Log error to journal/console.
                pass

        if project.dev_overrides:
            project.dev_env.update(project.dev_overrides)

        return project
