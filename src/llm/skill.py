# src/llm/skill.py

"""Skill module for parsing LLM skills from markdown files."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass
class Skill:
    """Represents a skill (prompt template + metadata)."""

    name: str
    description: str
    system_prompt: str
    user_invocable: bool = False

    @classmethod
    def from_file(cls, path: Path) -> "Skill":
        """Load skill from a markdown file with frontmatter."""
        if not path.is_file():
            raise FileNotFoundError(f"Skill file not found: {path}")

        content = path.read_text(encoding="utf-8")
        parts = content.split("---", 2)

        if len(parts) < 3:
            raise ValueError(f"Invalid skill file format (missing frontmatter): {path}")

        # Example with frontmatter package
        # import frontmatter  # pip install frontmatter
        # post = frontmatter.load("rtl-verifier/SKILL.md")
        # fm = post.metadata
        # body = post.content
        try:
            frontmatter = yaml.safe_load(parts[1])
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML frontmatter in {path}: {e}") from e

        body = parts[2].strip()

        return cls(
            name=frontmatter.get("name", path.stem),
            description=frontmatter.get("description", ""),
            user_invocable=frontmatter.get("user-invocable", False),
            system_prompt=body,
        )

    def render_system_prompt(self, **kwargs: Any) -> str:
        """Render the system prompt with context variables."""
        try:
            return self.system_prompt.format(**kwargs)
        except KeyError as e:
            raise ValueError(f"Missing context variable for skill {self.name}: {e}") from e
