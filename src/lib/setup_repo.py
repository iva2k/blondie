# src/lib/setup_repo.py

"""Helper to setup a development repository with a local remote."""

import os
import shutil
import stat
import subprocess
from pathlib import Path


def handle_remove_readonly(func, path, _):
    """Handle read-only files during rmtree (Windows fix)."""
    os.chmod(path, stat.S_IWRITE)
    func(path)


def run_command(args: list[str], cwd: Path) -> None:
    """Run a shell command."""
    subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True)


def setup_repo(
    repo_dir: Path, remote_dir: Path, agent_config_path: Path | None = None, root_dir: Path | None = None
) -> None:
    """
    Setup a temporary development environment with a local remote.

    Args:
        repo_dir: Path to the local working repository.
        remote_dir: Path to the bare remote repository.
        agent_config_path: Path to .agent configuration to copy (optional).
        root_dir: Root directory of the blondie project (to find llm.yaml).
    """
    # 1. Clean up previous run
    for path in [repo_dir, remote_dir]:
        if path.exists():
            # TODO: (now) The function "rmtree" is deprecated. The `onerror` parameter is deprecated. Use `onexc` instead.
            shutil.rmtree(path, onerror=handle_remove_readonly)

    # 2. Create Bare Remote
    remote_dir.mkdir(parents=True, exist_ok=True)
    run_command(["git", "init", "--bare"], cwd=remote_dir)

    # 3. Create Local Repo
    repo_dir.mkdir(parents=True, exist_ok=True)
    run_command(["git", "init"], cwd=repo_dir)

    # 4. Configure Remote
    remote_str = str(remote_dir.resolve())
    run_command(["git", "remote", "add", "origin", remote_str], cwd=repo_dir)

    # 5. Configure User (Required for commits in CI/Test envs)
    run_command(["git", "config", "user.name", "Blondie Dev"], cwd=repo_dir)
    run_command(["git", "config", "user.email", "dev@blondie.ai"], cwd=repo_dir)

    # 6. Bootstrap Content
    (repo_dir / "README.md").write_text("# Dev Repo\n\nTest repo for Blondie development.\n", encoding="utf-8")

    # Copy .agent configuration if provided
    if agent_config_path and agent_config_path.exists():
        shutil.copytree(agent_config_path, repo_dir / ".agent")
    else:
        # Create empty .agent dir if no config provided
        (repo_dir / ".agent").mkdir(exist_ok=True)

    # Handle secrets and cached data
    if root_dir:
        target_agent_dir = repo_dir / ".agent"
        target_agent_dir.mkdir(exist_ok=True)

        # 1. Copy local llm.yaml (cached models/costs)
        src_llm_yaml = root_dir / ".agent" / "llm.yaml"
        if src_llm_yaml.is_file():
            shutil.copy2(src_llm_yaml, target_agent_dir / "llm.yaml")

        # 2. Copy secrets.env.yaml if exists (Real E2E), else create dummy (Mocked E2E)
        src_secrets = root_dir / ".agent" / "secrets.env.yaml"
        target_secrets = target_agent_dir / "secrets.env.yaml"
        if src_secrets.is_file():
            shutil.copy2(src_secrets, target_secrets)
        elif not target_secrets.exists():
            target_secrets.write_text("llm: {}", encoding="utf-8")

    # 7. Initial Commit & Push
    run_command(["git", "checkout", "-b", "main"], cwd=repo_dir)
    run_command(["git", "add", "."], cwd=repo_dir)
    run_command(["git", "commit", "-m", "Initial commit"], cwd=repo_dir)
    run_command(["git", "push", "-u", "origin", "main"], cwd=repo_dir)
