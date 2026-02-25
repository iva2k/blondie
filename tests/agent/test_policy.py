# tests/agent/test_policy.py

"""Policy parser unit tests."""

from pathlib import Path

import pytest

from agent.policy import Policy


@pytest.fixture
def sample_policy_file(tmp_path: Path) -> Path:
    """Create sample POLICY.yaml for testing."""
    policy_file = tmp_path / "POLICY.yaml"
    policy_file.write_text(
        """
autonomy:
  gates:
    git-merge: prompt
    deploy-prod: prompt
    install-binary: forbid
commands:
  test: "npm test"
  build: "npm run build"
docs:
  always-update:
    - README.md
""",
        encoding="utf-8",
    )
    return policy_file


def test_policy_yaml_parsing(sample_policy_file: Path) -> None:
    """Test YAML yaml parsing."""
    policy = Policy.from_file(sample_policy_file)

    assert policy.check_permission("git-merge") == "prompt"
    assert policy.check_permission("deploy-prod") == "prompt"
    assert policy.check_permission("install-binary") == "forbid"
    assert policy.get_command("test") == "npm test"
    assert policy.docs["always-update"] == ["README.md"]


def test_default_allow() -> None:
    """Test default allow behavior."""
    policy = Policy()
    assert policy.check_permission("anything") == "allow"


def test_policy_structure(sample_policy_file: Path) -> None:
    """Test that gates are not flattened to top level."""
    policy = Policy.from_file(sample_policy_file)
    assert not hasattr(policy, "gates")
    assert policy.autonomy["gates"]["git-merge"] == "prompt"
