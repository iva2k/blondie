"""Tests for template integrity."""

from pathlib import Path

import pytest
import yaml

# Discover templates dynamically
ROOT_DIR = Path(__file__).parents[2]
TEMPLATES_DIR = ROOT_DIR / "templates"
TEMPLATES = [d.name for d in TEMPLATES_DIR.iterdir() if d.is_dir() and not d.name.startswith(".")]


@pytest.mark.parametrize("template_name", TEMPLATES)
def test_template_structure(template_name):
    """Ensure template has all required files."""
    template_dir = TEMPLATES_DIR / template_name
    required_files = [
        ".agent/project.yaml",
        ".agent/POLICY.yaml",
        ".agent/llm_config.yaml",
        ".agent/dev.yaml",
        ".agent/TASKS.md",
        ".agent/SPEC.md",
        ".agent/ISSUES.md",
        ".gitignore",
        ".agent/secrets.env.EXAMPLE.yaml",
    ]

    for filename in required_files:
        file_path = template_dir / filename
        assert file_path.exists(), f"Missing {filename} in {template_name} template"


@pytest.mark.parametrize("template_name", TEMPLATES)
def test_template_valid_yaml(template_name):
    """Ensure YAML files in template are valid."""
    template_dir = TEMPLATES_DIR / template_name
    # Find all yaml files in the template directory recursively
    yaml_files = list(template_dir.rglob("*.yaml")) + list(template_dir.rglob("*.yml"))

    for file_path in yaml_files:
        with open(file_path, encoding="utf-8") as f:
            try:
                yaml.safe_load(f)
            except yaml.YAMLError as e:
                pytest.fail(f"Invalid YAML in {template_name}/{file_path.name}: {e}")
