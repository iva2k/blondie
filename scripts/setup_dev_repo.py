#!/usr/bin/env python3
# scripts/setup_dev_repo.py

"""
Setup a temporary development environment with a local remote.

Creates:
  <repo>            (Local working repo connected to remote)
  <repo>-remote.git (Bare repo acting as origin)
"""

import argparse
import sys
from pathlib import Path

# Constants
ROOT_DIR = Path(__file__).resolve().parent.parent

# Add src to path to allow imports
sys.path.append(str(ROOT_DIR / "src"))


def parse_args() -> argparse.Namespace:
    """Parse command args."""
    parser = argparse.ArgumentParser(description="Setup a temporary development environment with a local remote.")
    parser.add_argument(
        "--repo",
        type=Path,
        default=ROOT_DIR / "_tmp" / "repo",
        help="Path to the local working repository",
    )
    parser.add_argument(
        "--remote",
        type=Path,
        default=None,
        help="Path to the bare remote repository (default: <repo>-remote.git)",
    )
    parser.add_argument(
        "--agent-config",
        type=Path,
        default=None,
        help="Path to .agent configuration to copy (optional)",
    )

    args = parser.parse_args()
    return args


def main() -> None:
    """CLI entry point."""
    # pylint: disable=import-outside-toplevel
    from lib.setup_repo import setup_repo

    args = parse_args()
    repo_dir = args.repo.resolve()

    if args.remote:
        remote_dir = args.remote.resolve()
    else:
        # Default: <repo>-remote.git
        remote_dir = Path(f"{str(repo_dir)}-remote.git")

    print(f"Setting up repo at {repo_dir}...")
    setup_repo(repo_dir, remote_dir, agent_config_path=args.agent_config, root_dir=ROOT_DIR)

    print("\n✅ Development environment ready!")
    print(f"   Working Repo: {repo_dir}")
    print(f"   Remote:       {remote_dir}")
    print("\nTo run agent against this repo:")
    print(f"   poetry run python -m agent.loop {repo_dir}")


if __name__ == "__main__":
    main()
