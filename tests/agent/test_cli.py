# tests/agent/test_cli.py

"""Unit tests for CLI entry point."""

from unittest.mock import AsyncMock, patch

import pytest
from click.testing import CliRunner

from agent.cli import entry_point, main


@pytest.mark.asyncio
async def test_main_v1():
    """Test main runs v1 agent by default."""
    with patch("agent.cli.BlondieAgent") as mock_agent:
        mock_instance = mock_agent.return_value
        mock_instance.run = AsyncMock()

        await main(repo_path=".", use_v2=False)

        mock_agent.assert_called_once()
        mock_instance.run.assert_called_once()


@pytest.mark.asyncio
async def test_main_v2():
    """Test main runs v2 orchestrator when requested."""
    with patch("agent.cli.BlondieOrchestrator") as mock_orch:
        mock_instance = mock_orch.return_value
        mock_instance.run = AsyncMock()

        await main(repo_path=".", use_v2=True)

        mock_orch.assert_called_once()
        mock_instance.run.assert_called_once()


def test_cli_entry_point():
    """Test CLI argument parsing."""
    runner = CliRunner()
    with patch("agent.cli.main", new_callable=AsyncMock) as mock_main:
        result = runner.invoke(entry_point, ["--v2"])
        assert result.exit_code == 0
        mock_main.assert_awaited_with(".", None, True)
