# src/agent/project.py

"""Project configuration parser."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel

from llm.journal import Journal


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
    dev_env: dict[str, Any] = {}

    @classmethod
    def from_file(cls, path: Path, journal: Journal | None = None) -> Project:
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
            # pylint: disable-next=broad-exception-caught
            except Exception as e:
                journal = journal or Journal()
                journal.print(f"❌ Failed to load dev_config {dev_path}: {e}")
        del project.dev_config  # Do not show it after loading
        return project
