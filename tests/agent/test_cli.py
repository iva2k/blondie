"""Tests for the CLI entry point."""

from unittest.mock import AsyncMock, patch

import pytest
from click.testing import CliRunner

from agent.cli import entry_point, main


def test_cli_help():
    """Test that the CLI shows help and subcommands."""
    runner = CliRunner()
    result = runner.invoke(entry_point, ["--help"])

    assert result.exit_code == 0
    assert "Blondie Agent CLI" in result.output
    assert "run" in result.output
    assert "init" in result.output


@patch("agent.cli.main")
def test_cli_run_command(mock_main):
    """Test the run subcommand."""
    runner = CliRunner()
    # Need a valid path for the argument type check (click.Path(exists=True))
    with runner.isolated_filesystem():
        result = runner.invoke(entry_point, ["run", "."])

        assert result.exit_code == 0
        mock_main.assert_called_once()


@patch("agent.cli.run_init_wizard")
def test_cli_init_command(mock_wizard):
    """Test the init subcommand."""
    runner = CliRunner()
    result = runner.invoke(entry_point, ["init"])

    assert result.exit_code == 0
    assert "Initialization Wizard" in result.output
    mock_wizard.assert_called_once()


@pytest.mark.asyncio
async def test_main_v1():
    """Test main function initializes BlondieAgent (v1)."""
    with patch("agent.cli.BlondieAgent") as mock_agent_cls:
        mock_instance = AsyncMock()
        mock_agent_cls.return_value = mock_instance
        mock_instance.run = AsyncMock()

        await main("/path/to/repo", journal_dir="/logs", use_v2=False)

        mock_agent_cls.assert_called_once_with("/path/to/repo", "/logs")
        mock_instance.run.assert_called_once()


@pytest.mark.asyncio
async def test_main_v2():
    """Test main function initializes BlondieOrchestrator (v2)."""
    with patch("agent.cli.BlondieOrchestrator") as mock_orch_cls:
        mock_instance = AsyncMock()
        mock_orch_cls.return_value = mock_instance
        mock_instance.run = AsyncMock()

        await main("/path/to/repo", journal_dir="/logs", use_v2=True)

        mock_orch_cls.assert_called_once_with("/path/to/repo", "/logs")
        mock_instance.run.assert_called_once()
