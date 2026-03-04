#!/usr/bin/env python3
# scripts/setup_dev_repo.py

"""
Setup a temporary development environment with a local remote.

Creates:
  <repo>            (Local working repo connected to remote)
  <repo>-remote.git (Bare repo acting as origin)
"""

import argparse
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

# Constants
ROOT_DIR = Path(__file__).resolve().parent.parent


def handle_remove_readonly(func, path, _):
    """Handle read-only files during rmtree (Windows fix)."""
    os.chmod(path, stat.S_IWRITE)
    func(path)


def run_command(args: list[str], cwd: Path) -> None:
    """Run a shell command."""
    try:
        subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        print(f"Error running {' '.join(args)} in {cwd}:")
        print(e.stderr)
        sys.exit(1)


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
    args = parse_args()
    repo_dir = args.repo.resolve()

    if args.remote:
        remote_dir = args.remote.resolve()
    else:
        # Default: <repo>-remote.git
        remote_dir = Path(f"{str(repo_dir)}-remote.git")

    # 1. Clean up previous run
    for path in [repo_dir, remote_dir]:
        if path.exists():
            print(f"Cleaning {path}...")
            # TODO: (now) The function "rmtree" is deprecated. The `onerror` parameter is deprecated. Use `onexc` instead.
            shutil.rmtree(path, onerror=handle_remove_readonly)

    # 2. Create Bare Remote
    print(f"Creating bare remote at {remote_dir}...")
    remote_dir.mkdir(parents=True)
    run_command(["git", "init", "--bare"], cwd=remote_dir)

    # 3. Create Local Repo
    print(f"Creating local repo at {repo_dir}...")
    repo_dir.mkdir(parents=True)
    run_command(["git", "init"], cwd=repo_dir)

    # 4. Configure Remote
    remote_str = str(remote_dir)  # Use absolute path for Windows compatibility
    run_command(["git", "remote", "add", "origin", remote_str], cwd=repo_dir)

    # 5. Bootstrap Content
    print("Bootstrapping repo content...")
    (repo_dir / "README.md").write_text("# Dev Repo\n\nTest repo for Blondie development.\n")

    # Copy .agent configuration if provided
    if args.agent_config:
        if args.agent_config.exists():
            print(f"Copying .agent config from {args.agent_config}...")
            shutil.copytree(args.agent_config, repo_dir / ".agent")
        else:
            print(f"Warning: Config path {args.agent_config} not found. Repo will lack .agent config.")

    # Copy local llm.yaml if exists (contains cached models/costs)
    local_llm_yaml = ROOT_DIR / ".agent" / "llm.yaml"
    if local_llm_yaml.is_file():
        target_agent_dir = repo_dir / ".agent"
        target_agent_dir.mkdir(exist_ok=True)
        print(f"Copying local llm.yaml from {local_llm_yaml}...")
        shutil.copy2(local_llm_yaml, target_agent_dir / "llm.yaml")

    # 6. Initial Commit & Push
    run_command(["git", "checkout", "-b", "main"], cwd=repo_dir)
    run_command(["git", "add", "."], cwd=repo_dir)
    run_command(["git", "commit", "-m", "Initial commit"], cwd=repo_dir)
    run_command(["git", "push", "-u", "origin", "main"], cwd=repo_dir)

    print("\n✅ Development environment ready!")
    print(f"   Working Repo: {repo_dir}")
    print(f"   Remote:       {remote_dir}")
    print("\nTo run agent against this repo:")
    print(f"   poetry run python -m agent.loop {repo_dir}")


if __name__ == "__main__":
    main()
