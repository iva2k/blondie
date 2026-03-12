# src/agent/wizard.py

"""Blondie Agent Initialization Wizard."""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import click
import yaml

from agent.lib.models import fetch_and_save_models


def setup_secrets() -> dict[str, Any]:
    """Interactive secrets setup."""
    click.echo("\n🔑 Secrets Setup")

    # Path inside container (mapped from host ~/.blondie) or local home
    secrets_dir = Path.home() / ".blondie"
    secrets_file = secrets_dir / "secrets.env.yaml"

    if not secrets_dir.exists():
        try:
            secrets_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            click.echo(f"Warning: Could not create {secrets_dir}: {e}")

    secrets: dict[str, Any] = {}
    if secrets_file.exists():
        click.echo(f"Found existing secrets at {secrets_file}")
        try:
            with open(secrets_file, encoding="utf-8") as f:
                secrets = yaml.safe_load(f) or {}
        except Exception as e:  # pylint: disable=broad-exception-caught
            click.echo(f"Error loading secrets: {e}")

    # Ensure structure
    secrets.setdefault("llm", {})
    secrets.setdefault("cloud", {})
    secrets.setdefault("git", {})

    # OpenAI
    if not secrets["llm"].get("openai", {}).get("api_key"):
        if click.confirm("Do you want to set up OpenAI API Key?", default=True):
            key = click.prompt("OpenAI API Key", hide_input=True)
            secrets["llm"]["openai"] = {"api_key": key}

    # Anthropic
    if not secrets["llm"].get("anthropic", {}).get("api_key"):
        if click.confirm("Do you want to set up Anthropic API Key?", default=False):
            key = click.prompt("Anthropic API Key", hide_input=True)
            secrets["llm"]["anthropic"] = {"api_key": key}

    # Cloud (Vercel)
    if not secrets["cloud"].get("vercel", {}).get("token"):
        if click.confirm("Do you want to set up Vercel Token?", default=False):
            token = click.prompt("Vercel Token", hide_input=True)
            secrets["cloud"]["vercel"] = {"token": token}

    # Git
    if not secrets["git"].get("github_token"):
        if click.confirm("Do you want to set up GitHub Token (for Push/PR)?", default=False):
            token = click.prompt("GitHub Token", hide_input=True)
            secrets["git"]["github_token"] = token

    # Save
    try:
        with open(secrets_file, "w", encoding="utf-8") as f:
            yaml.safe_dump(secrets, f)
        click.echo(f"✅ Secrets saved to {secrets_file}")
    except OSError as e:
        click.echo(f"❌ Failed to write secrets: {e}")

    return secrets


def validate_secrets(secrets: dict[str, Any]) -> None:
    """Validate secrets by fetching models (Task 103)."""
    click.echo("\n📡 Validating Keys & Fetching Models...")

    # Determine workspace path (mapped to /workspace in Docker)
    workspace = Path("/workspace")
    if not workspace.exists():
        # Fallback for local dev
        workspace = Path.cwd()

    llm_yaml_path = workspace / ".agent" / "llm.yaml"

    success = asyncio.run(fetch_and_save_models(secrets, llm_yaml_path, log_func=click.echo))

    if success:
        click.echo(f"✅ Model list saved to {llm_yaml_path}")
    else:
        click.echo("⚠️  Could not verify any API keys. Please check your secrets.")


def setup_workspace(target_dir: Path | None = None) -> None:
    """Initialize workspace with git and templates (Task 105)."""
    click.echo("\n🛠️  Workspace Setup")

    # Determine workspace path
    if target_dir:
        workspace = target_dir
    else:
        workspace = Path("/workspace")
        if not workspace.exists():
            workspace = Path.cwd()

    click.echo(f"Target: {workspace}")

    # 1. Git Init
    if not (workspace / ".git").exists():
        if click.confirm("Initialize git repository?", default=True):
            try:
                subprocess.run(["git", "init", str(workspace)], check=True, capture_output=True)
                click.echo("✅ Initialized empty git repository")
            except subprocess.CalledProcessError as e:
                click.echo(f"❌ git init failed: {e}")
    else:
        click.echo("✅ Git repository detected")

    # 2. Copy Templates
    # Resolves to .../blondie/templates/basic assuming src/agent/wizard.py location
    template_dir = Path(__file__).parents[2] / "templates" / "basic"

    if not template_dir.exists():
        click.echo(f"⚠️  Templates not found at {template_dir}. Skipping template copy.")
        return

    agent_dir = workspace / ".agent"
    agent_dir.mkdir(exist_ok=True)

    # Config files to go into .agent/
    config_files = [
        "project.yaml",
        "POLICY.yaml",
        "llm_config.yaml",
        "dev.yaml",
        "TASKS.md",
        "SPEC.md",
        "ISSUES.md",
        "secrets.env.EXAMPLE.yaml",
    ]

    for filename in config_files:
        src = template_dir / filename
        dest = agent_dir / filename

        if not src.exists():
            continue

        if dest.exists():
            if not click.confirm(f"Overwrite .agent/{filename}?", default=False):
                continue

        shutil.copy2(src, dest)
        click.echo(f"Created .agent/{filename}")

    # .gitignore (Root)
    gitignore_src = template_dir / ".gitignore"
    gitignore_dest = workspace / ".gitignore"

    if gitignore_src.exists():
        new_content = gitignore_src.read_text(encoding="utf-8")
        if gitignore_dest.exists():
            current_content = gitignore_dest.read_text(encoding="utf-8")
            # Simple check to avoid duplication of the block
            if ".agent/secrets.env.yaml" not in current_content:
                with open(gitignore_dest, "a", encoding="utf-8") as f:
                    f.write("\n" + new_content)
                click.echo("Updated .gitignore")
        else:
            shutil.copy2(gitignore_src, gitignore_dest)
            click.echo("Created .gitignore")

    # 3. Fix Permissions (Docker/Linux)
    # If running as root (Docker default), chown created files to match workspace owner
    if hasattr(os, "getuid") and os.getuid() == 0:  # type: ignore # pylint: disable=no-member
        try:
            stat = workspace.stat()
            uid, gid = stat.st_uid, stat.st_gid

            # recursive chown .agent
            for root, dirs, files in os.walk(agent_dir):
                for d in dirs:
                    os.chown(os.path.join(root, d), uid, gid)  # type: ignore # pylint: disable=no-member
                for filename in files:
                    os.chown(os.path.join(root, filename), uid, gid)  # type: ignore # pylint: disable=no-member
            os.chown(agent_dir, uid, gid)  # type: ignore # pylint: disable=no-member

            # chown .gitignore
            if gitignore_dest.exists():
                os.chown(gitignore_dest, uid, gid)  # type: ignore # pylint: disable=no-member

            click.echo("✅ Fixed file permissions")
        except Exception as e:  # pylint: disable=broad-exception-caught
            click.echo(f"⚠️  Failed to set permissions: {e}")


def run_init_wizard() -> None:
    """Run the full initialization wizard."""
    secrets = setup_secrets()
    validate_secrets(secrets)
    setup_workspace()
