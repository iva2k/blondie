"""Unit tests for Shell Command Policy module."""

from unittest.mock import Mock

import pytest

from agent.interaction import InteractionProvider
from agent.shell_cmd_policy import ShellCommandPolicy


class MockPolicy:
    """Mock policy for testing."""

    def __init__(self, permissions=None):
        self.permissions = permissions or {}

    def check_permission(self, action):
        """Check permission for action."""
        return self.permissions.get(action, "allow")


class MockInteractionProvider(InteractionProvider):
    """Mock interaction provider for testing."""

    def __init__(self, responses=None):
        self.responses = responses or []
        self.prompt_calls = []

    def prompt_user(self, message: str) -> bool:
        self.prompt_calls.append(message)
        if self.responses:
            return self.responses.pop(0)
        return False


@pytest.fixture
def policy():
    """Fixture for mock policy."""
    return MockPolicy()


@pytest.fixture
def journal():
    """Fixture for mock journal."""
    return Mock()


@pytest.fixture
def interactor():
    """Fixture for mock interactor."""
    return MockInteractionProvider()


@pytest.fixture
def cmd_policy(policy, journal, interactor):
    """Fixture for shell command policy."""
    return ShellCommandPolicy(policy, journal, interactor)


def test_check_allowed_by_default(cmd_policy):
    """Test that commands are allowed when policy allows."""
    cmd_policy.policy.permissions = {}  # Default allow
    allowed, reason = cmd_policy.check("echo hello")
    assert allowed is True
    assert reason is None


def test_check_forbidden_shell_files(cmd_policy):
    """Test blocking of shell file writes."""
    cmd_policy.policy.permissions = {"shell-files": "forbid"}
    allowed, reason = cmd_policy.check("echo 'secret' > .env")
    assert allowed is False
    assert "BLOCKED" in reason
    assert "tool calls" in reason


def test_check_forbidden_package(cmd_policy):
    """Test blocking of package installation."""
    cmd_policy.policy.permissions = {"add-package": "forbid"}
    allowed, reason = cmd_policy.check("npm install malicious")
    assert allowed is False
    assert reason == "SKIPPED_BY_POLICY"


def test_check_prompt_flow(cmd_policy, interactor):
    """Test interactive prompt flow."""
    cmd_policy.policy.permissions = {"add-package": "prompt"}

    # User approves
    interactor.responses = [True]
    allowed, reason = cmd_policy.check("npm install nice-lib")
    assert allowed is True
    assert "add-package" in interactor.prompt_calls[0]

    # User denies
    interactor.responses = [False]
    allowed, reason = cmd_policy.check("npm install bad-lib")
    assert allowed is False
    assert reason == "SKIPPED_BY_USER"


def test_check_complex_chain(cmd_policy):
    """Test checking a chain of commands where one is forbidden."""
    cmd_policy.policy.permissions = {"shell-files": "forbid"}

    # Safe command first, then dangerous
    allowed, reason = cmd_policy.check("ls -la && echo x > y")
    assert allowed is False
    assert "BLOCKED" in reason

    # Dangerous first
    allowed, reason = cmd_policy.check("echo x > y; ls -la")
    assert allowed is False


def test_check_default_gate_override(cmd_policy):
    """Test that default_gate argument overrides/adds to checks."""
    cmd_policy.policy.permissions = {"custom-gate": "forbid"}

    # Command itself is safe, but gated by caller
    allowed, reason = cmd_policy.check("ls -la", default_gate="custom-gate")
    assert allowed is False
    assert reason == "SKIPPED_BY_POLICY"


def test_escape_attempts_sudo(cmd_policy):
    """Test detection even when sudo is used."""
    cmd_policy.policy.permissions = {"shell-files": "forbid"}

    allowed, _reason = cmd_policy.check("sudo echo '127.0.0.1' > /etc/hosts")
    assert allowed is False

    allowed, _reason = cmd_policy.check("echo '127.0.0.1' | sudo tee /etc/hosts")
    assert allowed is False


def test_escape_attempts_subshell_redirection(cmd_policy):
    """Test detection inside subshells (heuristic)."""
    cmd_policy.policy.permissions = {"shell-files": "forbid"}

    # The splitter doesn't handle subshells, so it sees the whole string.
    # The gate detector checks for '>' in the string.
    allowed, _reason = cmd_policy.check("echo $(cat x > y)")
    assert allowed is False


def test_escape_attempts_quoted_redirection(cmd_policy):
    """Test behavior with quoted redirection characters."""
    # This is a known limitation/feature: quotes don't hide the > from the simple check
    cmd_policy.policy.permissions = {"shell-files": "forbid"}

    # False positive scenario: echoing a string with >
    allowed, _reason = cmd_policy.check('echo "Look at this > arrow"')
    assert allowed is False  # Conservative blocking


def test_escape_attempts_pipe_chain(cmd_policy):
    """Test detection in long pipe chains."""
    cmd_policy.policy.permissions = {"shell-files": "forbid"}

    allowed, _reason = cmd_policy.check("cat file | grep x | sort | uniq > output.txt")
    # 'uniq > output.txt' is the last part.
    # 'uniq' is NOT in [echo, printf, cat].
    # So this specific command is actually ALLOWED by the current logic.
    # The logic only blocks echo/printf/cat > file.
    assert allowed is True

    # But if we use cat at the end
    allowed, _reason = cmd_policy.check("grep x file | cat > output.txt")
    assert allowed is False
