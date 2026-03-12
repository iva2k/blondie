"""Tests for template integrity."""

from pathlib import Path

import pytest
import yaml


def test_basic_template_structure():
    """Ensure templates/basic has all required files."""
    root = Path(__file__).parents[2]
    template_dir = root / "templates" / "basic"

    assert template_dir.exists(), "Basic template directory missing"

    required_files = [
        "project.yaml",
        "POLICY.yaml",
        "llm_config.yaml",
        "dev.yaml",
        "TASKS.md",
        "SPEC.md",
        "ISSUES.md",
        ".gitignore",
        "secrets.env.EXAMPLE.yaml",
    ]

    for filename in required_files:
        file_path = template_dir / filename
        assert file_path.exists(), f"Missing {filename} in basic template"


def test_basic_template_valid_yaml():
    """Ensure YAML files in template are valid."""
    root = Path(__file__).parents[2]
    template_dir = root / "templates" / "basic"

    yaml_files = ["project.yaml", "POLICY.yaml", "llm_config.yaml", "dev.yaml", "secrets.env.EXAMPLE.yaml"]

    for filename in yaml_files:
        path = template_dir / filename
        with open(path, encoding="utf-8") as f:
            try:
                yaml.safe_load(f)
            except yaml.YAMLError as e:
                pytest.fail(f"Invalid YAML in {filename}: {e}")
