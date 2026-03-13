"""Tests for the CLI entry point."""

import io
import zipfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

from agent.cli import SetupRequestHandler, entry_point, main


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
async def test_main_v1(tmp_path):
    """Test main function initializes BlondieAgent (v1)."""
    with patch("agent.cli.BlondieAgent") as mock_agent_cls:
        mock_instance = AsyncMock()
        mock_agent_cls.return_value = mock_instance
        mock_instance.run = AsyncMock()

        # Setup configured state
        (tmp_path / ".agent").mkdir()
        (tmp_path / ".agent" / "project.yaml").touch()

        await main(str(tmp_path), journal_dir="/logs", use_v2=False)

        mock_agent_cls.assert_called_once_with(str(tmp_path), "/logs")
        mock_instance.run.assert_called_once()


@pytest.mark.asyncio
async def test_main_v2(tmp_path):
    """Test main function initializes BlondieOrchestrator (v2)."""
    with patch("agent.cli.BlondieOrchestrator") as mock_orch_cls:
        mock_instance = AsyncMock()
        mock_orch_cls.return_value = mock_instance
        mock_instance.run = AsyncMock()

        # Setup configured state
        (tmp_path / ".agent").mkdir()
        (tmp_path / ".agent" / "project.yaml").touch()

        await main(str(tmp_path), journal_dir="/logs", use_v2=True)

        mock_orch_cls.assert_called_once_with(str(tmp_path), "/logs")
        mock_instance.run.assert_called_once()


@pytest.mark.asyncio
async def test_main_unconfigured(tmp_path):
    """Test main function enters setup mode if unconfigured."""
    with patch("agent.cli.wait_for_configuration") as mock_wait:
        with patch("agent.cli.BlondieAgent") as mock_agent_cls:
            mock_instance = AsyncMock()
            mock_agent_cls.return_value = mock_instance

            # No .agent/project.yaml

            await main(str(tmp_path), use_v2=False)

            mock_wait.assert_called_once()
            # Should proceed to run after wait returns
            mock_instance.run.assert_called_once()


def test_setup_handler_post(tmp_path):
    """Test the HTTP handler for receiving zip config."""
    # Create a mock zip
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as z:
        z.writestr(".agent/project.yaml", "id: test")
        z.writestr(".agent/ssh/id_rsa", "ssh-key-content")

    zip_content = zip_buffer.getvalue()

    # Mock Request and Server
    request = MagicMock()
    # Mock rfile (read body)
    request.makefile.return_value = io.BytesIO(zip_content)

    # We need to mock the socket/rfile/wfile interactions of BaseHTTPRequestHandler
    # It's easier to mock the handler methods directly or setup a complex mock structure.
    # Alternatively, construct the handler with mocks.

    class MockServer:
        repo_path = tmp_path

        def shutdown(self):
            pass

    # Mock input stream for rfile
    rfile = io.BytesIO(zip_content)
    wfile = io.BytesIO()

    handler = SetupRequestHandler(request, ("0.0.0.0", 8000), MockServer())
    handler.rfile = rfile
    handler.wfile = wfile
    handler.path = "/configure"
    handler.headers = {"content-length": str(len(zip_content))}
    handler.command = "POST"

    # We need to prevent handle() from running automatically or mock it?
    # BaseHTTPRequestHandler __init__ calls handle() which calls handle_one_request().
    # But we can instantiate it and then call do_POST if we mock correctly.
    # Actually, instantiating it triggers the whole request cycle if request is passed.
    # A common way to test is to override setup() or handle().

    # Let's just call do_POST on an instance initialized with dummy request?
    # It's tricky because __init__ runs everything.
    # Let's bypass __init__ and setup manually
    handler = SetupRequestHandler.__new__(SetupRequestHandler)
    handler.server = MockServer()
    handler.path = "/configure"
    handler.headers = {"content-length": str(len(zip_content))}
    handler.rfile = rfile
    handler.wfile = wfile

    # Add attributes required by BaseHTTPRequestHandler methods for logging/response
    handler.requestline = "POST /configure HTTP/1.1"
    handler.request_version = "HTTP/1.1"
    handler.protocol_version = "HTTP/1.1"
    handler.client_address = ("127.0.0.1", 12345)

    # Run logic
    with patch("shutil.copy2") as mock_copy, patch("pathlib.Path.chmod") as mock_chmod:
        # Patch Path.home to point to tmp_path so we don't mess with real .ssh
        with patch("pathlib.Path.home", return_value=tmp_path):
            handler.do_POST()

            # Check extracted
            assert (tmp_path / ".agent" / "project.yaml").exists()

            # Check SSH handling
            mock_copy.assert_called()
            mock_chmod.assert_called_with(0o600)

            # Check response
            # The response is complex, let's just check for the body
            assert b"Configuration received" in wfile.getvalue()
