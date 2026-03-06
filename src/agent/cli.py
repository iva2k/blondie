# src/agent/cli.py

"""Blondie Agent CLI."""

import asyncio

import click

from agent.loop import BlondieAgent
from agent.loop2 import BlondieOrchestrator


async def main(repo_path: str, journal_dir: str | None = None, use_v2: bool = False) -> None:
    """CLI entry point."""
    if use_v2:
        orchestrator = BlondieOrchestrator(repo_path, journal_dir)
        await orchestrator.run()
    else:
        agent = BlondieAgent(repo_path, journal_dir)
        await agent.run()


@click.command()
@click.argument("repo_path", default=".", type=click.Path(exists=True, file_okay=False, dir_okay=True))
@click.option(
    "--journal-dir",
    default=None,
    help="Directory to store journal logs",
    type=click.Path(file_okay=False, dir_okay=True),
)
@click.option("--v2", is_flag=True, help="Run v2 recursive orchestrator.")
def entry_point(repo_path: str = ".", journal_dir: str | None = None, v2: bool = False) -> None:
    """Blondie Agent CLI."""
    asyncio.run(main(repo_path, journal_dir, v2))


if __name__ == "__main__":
    entry_point()
