"""Policy parser unit tests."""

from pathlib import Path

import pytest

from src.agent.policy import Policy


@pytest.fixture
def sample_policy_file(tmp_path: Path) -> Path:
    """Create sample POLICY.md for testing."""
    policy_file = tmp_path / "POLICY.md"
    policy_file.write_text(
        """---
gates:
  git-merge: prompt
  deploy-prod: prompt
  install-binary: forbid
commands:
  test: "npm test"
  build: "npm run build"
---

## Autonomy Gates
git-merge: prompt
deploy-prod: prompt
""",
        encoding="utf-8",
    )
    return policy_file


def test_policy_yaml_parsing(policy_file: Path) -> None:
    """Test YAML frontmatter parsing."""
    policy = Policy.from_file(policy_file)

    assert policy.check_permission("git-merge") == "prompt"
    assert policy.check_permission("deploy-prod") == "prompt"
    assert policy.check_permission("install-binary") == "forbid"
    assert policy.check_permission("random-action") == "allow"
    assert policy.get_command("test") == "npm test"


def test_policy_markdown_fallback(tmp_path: Path) -> None:
    """Test markdown-only parsing."""
    policy_file = tmp_path / "POLICY.md"
    policy_file.write_text(
        """## Autonomy Gates
git-merge: prompt
deploy-prod: prompt

## Commands
test: npm test
build: npm run build""",
        encoding="utf-8",
    )

    policy = Policy.from_file(policy_file)
    assert policy.check_permission("git-merge") == "prompt"
    assert policy.get_command("test") == "npm test"


def test_default_allow() -> None:
    """Test default allow behavior."""
    policy = Policy()
    assert policy.check_permission("anything") == "allow"
