# src/agent/cli.py

"""Blondie Agent CLI."""

import asyncio
import io
import shutil
import threading
import zipfile
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import click

from agent.loop import BlondieAgent
from agent.loop2 import BlondieOrchestrator
from agent.wizard import run_init_wizard


class SetupRequestHandler(BaseHTTPRequestHandler):
    """Handle configuration upload."""

    def do_POST(self) -> None:  # pylint: disable=invalid-name
        """Receive and apply configuration zip."""
        if self.path != "/configure":
            self.send_error(404)
            return

        length = int(self.headers.get("content-length", 0))
        data = self.rfile.read(length)

        try:
            repo_path = self.server.repo_path  # type: ignore
            with zipfile.ZipFile(io.BytesIO(data)) as z_file:
                # Basic validation
                if ".agent/project.yaml" not in z_file.namelist():
                    self.send_error(400, "Invalid config: missing .agent/project.yaml")
                    return

                # Extract to repo_path
                z_file.extractall(repo_path)

            # Handle SSH if present (bundled in .agent/ssh/id_rsa)
            ssh_key = repo_path / ".agent" / "ssh" / "id_rsa"
            if ssh_key.exists():
                # Move to ~/.ssh/id_rsa
                ssh_home = Path.home() / ".ssh"
                ssh_home.mkdir(exist_ok=True, mode=0o700)
                dest = ssh_home / "id_rsa"
                shutil.copy2(ssh_key, dest)
                dest.chmod(0o600)
                print(f"🔑 Installed SSH key to {dest}")

            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Configuration received. Starting agent...")

            # Signal server to stop
            threading.Thread(target=self.server.shutdown).start()

        except zipfile.BadZipFile:
            self.send_error(400, "Invalid zip file")
        except Exception as e:  # pylint: disable=broad-exception-caught
            self.send_error(500, str(e))


def wait_for_configuration(repo_path: Path, port: int = 8000) -> None:
    """Start a blocking HTTP server to receive configuration."""
    click.echo(f"⚠️  Agent unconfigured (no .agent/project.yaml). Listening on port {port}...")
    server = HTTPServer(("0.0.0.0", port), SetupRequestHandler)
    server.repo_path = repo_path  # type: ignore
    server.serve_forever()
    click.echo("✅ Configuration applied.")


async def main(repo_path: str, journal_dir: str | None = None, use_v2: bool = False) -> None:
    """CLI entry point."""
    repo = Path(repo_path)
    if not (repo / ".agent" / "project.yaml").exists():
        # Run setup server if unconfigured
        # This blocks until configuration is received via POST /configure
        # We run this in the main thread/loop because we can't proceed without config.
        # Ideally this should be non-blocking but CLI main assumes configured state for loops.
        # For Docker usage, blocking here is fine.
        # We check if we are in an interactive TTY? No, assume daemon mode if calling run.
        # If interactive, user should have used 'init'.
        try:
            # Use thread or asyncio? HTTPServer is blocking.
            # Just run it.
            await asyncio.to_thread(wait_for_configuration, repo)
        except OSError as e:
            click.echo(f"❌ Failed to start setup server: {e}")
            return

    if use_v2:
        orchestrator = BlondieOrchestrator(repo_path, journal_dir)
        await orchestrator.run()
    else:
        agent = BlondieAgent(repo_path, journal_dir)
        await agent.run()


@click.group()
def entry_point() -> None:
    """Blondie Agent CLI."""


@entry_point.command()
@click.argument("repo_path", default=".", type=click.Path(exists=True, file_okay=False, dir_okay=True))
@click.option(
    "--journal-dir",
    default=None,
    help="Directory to store journal logs",
    type=click.Path(file_okay=False, dir_okay=True),
)
@click.option("--v2", is_flag=True, help="Run v2 recursive coding_orchestrator.")
def run(repo_path: str = ".", journal_dir: str | None = None, v2: bool = False) -> None:
    """Run the Blondie Agent loop."""
    asyncio.run(main(repo_path, journal_dir, v2))


@entry_point.command()
def init() -> None:
    """Initialize a new Blondie agent workspace."""
    click.echo("🧙 Blondie Agent Initialization Wizard")
    run_init_wizard()


if __name__ == "__main__":
    entry_point()
