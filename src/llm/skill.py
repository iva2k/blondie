# src/llm/skill.py

"""Skill module for parsing LLM skills from markdown files."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field


class FileEdit(BaseModel):
    """Schema for File Edit."""

    path: str | None = Field(None, description="File path relative to repo root")
    action: Literal["create", "edit", "delete", "shell"] = Field(..., description="Action to perform")
    instruction: str | None = Field(None, description="Instruction for file editing or creation")
    command: str | None = Field(None, description="Shell command to execute")
    timeout: int = Field(120, description="Timeout for shell command in seconds")


class FileEdits(BaseModel):
    """Schema for File Edits."""

    edits: list[FileEdit]


SKILL_MODELS = {
    "FileEdits": FileEdits,
}


@dataclass
class Skill:
    """Represents a skill (prompt template + metadata)."""

    name: str
    description: str
    system_prompt: str
    user_content: str | None
    operation: str = "coding"  # | "planning" | "coding" | "debugging" | "review"
    user_invocable: bool = False
    log_title: str = ""
    temperature: float = 0.1
    max_tokens: int = 2000
    context: dict[str, bool] | None = None
    response_schema: Any | None = None
    response_format: Literal["json", "yaml"] | None = None
    tools: list[str] | None = None

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

        schema_name = frontmatter.get("response-schema")
        response_schema = SKILL_MODELS.get(schema_name) if schema_name else None

        return cls(
            name=frontmatter.get("name", path.stem),
            description=frontmatter.get("description", ""),
            system_prompt=body,
            user_content=frontmatter.get("user-content", None),
            operation=frontmatter.get("operation", "coding"),
            user_invocable=frontmatter.get("user-invocable", False),
            log_title=frontmatter.get("log-title", ""),
            temperature=frontmatter.get("temperature", 0.1),
            max_tokens=frontmatter.get("max-tokens", 2000),
            context=frontmatter.get("context", None),
            response_schema=response_schema,
            response_format=frontmatter.get("response-format", None),
            tools=frontmatter.get("tools", None),
        )

    def render_system_prompt(self, **kwargs: Any) -> str:
        """Render the system prompt with context variables."""
        try:
            return self.system_prompt.format(**kwargs)
        except KeyError as e:
            raise ValueError(f"Missing context variable for skill {self.name}: {e}") from e
