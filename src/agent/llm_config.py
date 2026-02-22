# src/llm/llm_config.py

"""LLM Configuration parser."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel


class ProviderConfig(BaseModel):
    """Configuration for an LLM provider."""

    api_type: Literal["openai", "anthropic"]
    base_url: str | None = None
    default_model: str | None = None


class OperationSelection(BaseModel):
    """Model selection for a specific operation."""

    provider: str
    model: str | None = None


class LLMConfig(BaseModel):
    """Main LLM configuration."""

    providers: dict[str, ProviderConfig] = {}
    operations: dict[str, list[OperationSelection]] = {}

    @classmethod
    def from_file(cls, path: Path) -> LLMConfig:
        """Parse llm_config.yaml."""
        if not path.exists():
            return cls()
        content = path.read_text(encoding="utf-8")
        data = yaml.safe_load(content) or {}
        return cls(**data)
