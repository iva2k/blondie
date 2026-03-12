"""Tests for the initialization wizard."""

from unittest.mock import patch

import click
import pytest
import yaml
from click.testing import CliRunner

from agent.wizard import setup_secrets, validate_secrets


@pytest.fixture
def mock_home(tmp_path):
    """Mock Path.home() to return a temp directory."""
    with patch("pathlib.Path.home", return_value=tmp_path):
        yield tmp_path


def test_setup_secrets_new_file(mock_home):
    """Test creating a new secrets file with interactive input."""
    # Simulate user inputs:
    # 1. OpenAI? Yes
    # 2. Key: sk-test
    # 3. Anthropic? No
    # 4. Vercel? No
    # 5. GitHub? No
    inputs = "y\nsk-test\nn\nn\nn\n"

    runner = CliRunner()
    # We invoke a dummy command to run the function in a click context,
    # or just use runner.invoke if we wrap it in a command.
    # But setup_secrets uses click.prompt/confirm directly.
    # The easiest way to test click interaction functions is wrapping them.

    @click.command()
    def cmd():
        setup_secrets()

    result = runner.invoke(cmd, input=inputs)

    assert result.exit_code == 0
    assert "Secrets Setup" in result.output
    assert "✅ Secrets saved" in result.output

    secrets_file = mock_home / ".blondie" / "secrets.env.yaml"
    assert secrets_file.exists()

    with open(secrets_file, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    assert data["llm"]["openai"]["api_key"] == "sk-test"
    assert "anthropic" not in data["llm"]
    assert "vercel" not in data["cloud"]
    assert "github_token" not in data.get("git", {})


def test_setup_secrets_existing_file(mock_home):
    """Test updating an existing secrets file."""
    secrets_dir = mock_home / ".blondie"
    secrets_dir.mkdir()
    secrets_file = secrets_dir / "secrets.env.yaml"

    existing_data = {"llm": {"openai": {"api_key": "sk-existing"}}, "cloud": {}}
    with open(secrets_file, "w", encoding="utf-8") as f:
        yaml.safe_dump(existing_data, f)

    # Inputs:
    # OpenAI check (skipped because exists)
    # Anthropic? Yes -> sk-ant
    # Vercel? No
    # GitHub? Yes -> gh-token
    inputs = "y\nsk-ant\nn\ny\ngh-token\n"

    @click.command()
    def cmd():
        setup_secrets()

    runner = CliRunner()
    result = runner.invoke(cmd, input=inputs)

    assert result.exit_code == 0
    assert "Found existing secrets" in result.output

    with open(secrets_file, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    assert data["llm"]["openai"]["api_key"] == "sk-existing"
    assert data["llm"]["anthropic"]["api_key"] == "sk-ant"
    assert data["git"]["github_token"] == "gh-token"


@patch("agent.wizard.fetch_and_save_models")
def test_validate_secrets_success(mock_fetch):
    """Test validation success path."""
    mock_fetch.return_value = True

    # Mock workspace path in wizard using a patch context on Path
    # However, validate_secrets uses Path("/workspace") or Path.cwd() fallback.
    # We rely on the fallback or mock Path.

    # Since we can't easily mock Path constructor for specific args globally,
    # we'll assume it falls back to cwd if /workspace doesn't exist.

    secrets = {"llm": {"openai": {"api_key": "sk-test"}}}

    @click.command()
    def cmd():
        validate_secrets(secrets)

    runner = CliRunner()
    result = runner.invoke(cmd)

    assert result.exit_code == 0
    assert "Validating Keys" in result.output
    assert "✅ Model list saved" in result.output
    mock_fetch.assert_called_once()


def test_setup_secrets_errors(mock_home):
    """Test error handling in setup_secrets."""
    # 1. Test mkdir OSError
    with patch("pathlib.Path.mkdir", side_effect=OSError("Permission denied")):
        runner = CliRunner()

        @click.command()
        def cmd():
            setup_secrets()

        result = runner.invoke(cmd, input="n\nn\nn\nn\n")
        assert "Warning: Could not create" in result.output

    # 2. Test yaml load error
    secrets_dir = mock_home / ".blondie"
    if not secrets_dir.exists():
        secrets_dir.mkdir()
    (secrets_dir / "secrets.env.yaml").write_text(":", encoding="utf-8")  # Invalid YAML

    runner = CliRunner()

    @click.command()
    def cmd_load():
        setup_secrets()

    result = runner.invoke(cmd_load, input="n\nn\nn\nn\n")
    assert "Error loading secrets" in result.output


@patch("agent.wizard.fetch_and_save_models")
def test_validate_secrets_failure(mock_fetch):
    """Test validation failure path."""
    mock_fetch.return_value = False

    runner = CliRunner()

    @click.command()
    def cmd():
        validate_secrets({})

    result = runner.invoke(cmd)
    assert "Could not verify any API keys" in result.output
