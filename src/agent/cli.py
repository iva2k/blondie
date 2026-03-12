# src/agent/cli.py

"""Blondie Agent CLI."""

import asyncio

import click

from agent.loop import BlondieAgent
from agent.loop2 import BlondieOrchestrator
from agent.wizard import setup_secrets


async def main(repo_path: str, journal_dir: str | None = None, use_v2: bool = False) -> None:
    """CLI entry point."""
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
    setup_secrets()


if __name__ == "__main__":
    entry_point()
