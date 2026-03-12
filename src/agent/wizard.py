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
    if os.environ.get("BLONDIE_SECRETS_DIR"):
        secrets_dir = Path(os.environ["BLONDIE_SECRETS_DIR"])
    else:
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


def stack_detection(target_dir: Path | None = None) -> None:
    """Detect project stack and configure environment (Task 107)."""
    click.echo("\n🔍 Stack Detection")

    # Determine workspace path
    if target_dir:
        workspace = target_dir
    else:
        workspace = Path("/workspace")
        if not workspace.exists():
            workspace = Path.cwd()

    agent_dir = workspace / ".agent"
    if not agent_dir.exists():
        click.echo("Skipping stack detection (no .agent directory).")
        return

    detected_stack = None
    commands: dict[str, str] = {}
    dev_env: dict[str, str] = {}
    languages: list[str] = []

    # 1. Python Detection
    if (workspace / "pyproject.toml").exists():
        content = (workspace / "pyproject.toml").read_text(encoding="utf-8")
        if "tool.poetry" in content:
            detected_stack = "Python (Poetry)"
            commands = {
                "install": "poetry install",
                "test": "poetry run pytest",
                "lint": "poetry run ruff check .",
                "format": "poetry run ruff format .",
            }
            dev_env = {"language": "python", "manager": "poetry"}
        else:
            detected_stack = "Python (Standard/Pip)"
            commands = {"install": "pip install -e .", "test": "pytest"}
            dev_env = {"language": "python", "manager": "pip"}
        languages = ["python"]
    elif (workspace / "requirements.txt").exists():
        detected_stack = "Python (requirements.txt)"
        commands = {"install": "pip install -r requirements.txt", "test": "pytest"}
        dev_env = {"language": "python", "manager": "pip"}
        languages = ["python"]

    # 2. Node Detection (Overrides Python if found, or simple priority for now)
    if (workspace / "package.json").exists() and not detected_stack:
        manager = "npm"
        if (workspace / "yarn.lock").exists():
            manager = "yarn"
        elif (workspace / "pnpm-lock.yaml").exists():
            manager = "pnpm"

        detected_stack = f"Node.js ({manager})"
        commands = {
            "install": f"{manager} install",
            "test": f"{manager} test",
            "build": f"{manager} run build",
        }
        dev_env = {"language": "javascript", "manager": manager}
        languages = ["javascript"]

    if not detected_stack:
        click.echo("No specific stack detected. Using generic defaults.")
        return

    click.echo(f"Detected: {detected_stack}")

    if click.confirm("Update project configuration with detected defaults?", default=True):
        try:
            project_file = agent_dir / "project.yaml"
            if project_file.exists():
                data = yaml.safe_load(project_file.read_text(encoding="utf-8")) or {}
                if languages:
                    data["languages"] = languages
                data.setdefault("commands", {}).update(commands)
                project_file.write_text(yaml.safe_dump(data), encoding="utf-8")
                click.echo("✅ Updated project.yaml commands")

            dev_file = agent_dir / "dev.yaml"
            if dev_file.exists():
                data = yaml.safe_load(dev_file.read_text(encoding="utf-8")) or {}
                data.setdefault("environment", {}).update(dev_env)
                dev_file.write_text(yaml.safe_dump(data), encoding="utf-8")
                click.echo("✅ Updated dev.yaml environment")
        except Exception as e:  # pylint: disable=broad-exception-caught
            click.echo(f"⚠️  Failed to update config: {e}")


def interview(target_dir: Path | None = None) -> None:
    """Collect project details and configure agent (Task 106)."""
    click.echo("\n🎤 Project Interview")

    # Determine workspace path
    if target_dir:
        workspace = target_dir
    else:
        workspace = Path("/workspace")
        if not workspace.exists():
            workspace = Path.cwd()

    agent_dir = workspace / ".agent"
    if not agent_dir.exists():
        click.echo("⚠️  .agent directory not found. Please run workspace setup first.")
        return

    # 1. Spec
    spec_file = agent_dir / "SPEC.md"
    default_goal = "A new project"
    spec_goal = click.prompt("What are you building?", default=default_goal)

    if spec_file.exists():
        content = spec_file.read_text(encoding="utf-8")
        # Replace placeholder if present
        placeholder = "Goal: <Describe your product goal here>"
        if placeholder in content:
            content = content.replace(placeholder, f"Goal: {spec_goal}")
            spec_file.write_text(content, encoding="utf-8")
        elif f"Goal: {spec_goal}" not in content:
            # Append if not already there
            with open(spec_file, "a", encoding="utf-8") as f:
                f.write(f"\nGoal: {spec_goal}\n")
    else:
        spec_file.write_text(f"# Product Spec\n\nGoal: {spec_goal}\n", encoding="utf-8")

    # 2. Project Config
    project_file = agent_dir / "project.yaml"
    project_data: dict[str, Any] = {}
    if project_file.exists():
        project_data = yaml.safe_load(project_file.read_text(encoding="utf-8")) or {}

    default_id = project_data.get("id", workspace.name)
    project_id = click.prompt("Project ID", default=default_id)
    project_data["id"] = project_id
    if "name" not in project_data or project_data["name"] == "My New Project":
        project_data["name"] = project_id

    git_user = click.prompt("Bot Git Name", default=project_data.get("git_user", "Blondie Bot"))
    project_data["git_user"] = git_user

    # 3. Model Provider
    llm_file = agent_dir / "llm_config.yaml"
    if llm_file.exists():
        llm_data = yaml.safe_load(llm_file.read_text(encoding="utf-8")) or {}
        provider = click.prompt(
            "Primary AI Provider", default="openai", type=click.Choice(["openai", "anthropic", "groq"])
        )

        if "operations" not in llm_data:
            llm_data["operations"] = {}

        model_map = {
            "openai": "gpt-4o",
            "anthropic": "claude-3-5-sonnet-20240620",
            "groq": "llama-3.3-70b-versatile",
        }
        selected_model = model_map.get(provider, "gpt-4o")

        for op in ["planning", "coding", "debugging", "review", "execution"]:
            if op not in llm_data["operations"]:
                llm_data["operations"][op] = []
            # Ensure list
            if not isinstance(llm_data["operations"][op], list):
                llm_data["operations"][op] = []

            # Prepend selected provider
            llm_data["operations"][op].insert(0, {"provider": provider, "model": selected_model})

        llm_file.write_text(yaml.safe_dump(llm_data), encoding="utf-8")

    # 4. Deployment
    deploy_target = click.prompt(
        "Deployment Target", default="docker", type=click.Choice(["docker", "vercel", "netlify", "custom"])
    )

    if "commands" not in project_data:
        project_data["commands"] = {}

    if deploy_target == "vercel":
        project_data["commands"]["deploy"] = "vercel --prod --token {{secret:cloud.vercel.token}}"
    elif deploy_target == "netlify":
        project_data["commands"]["deploy"] = "netlify deploy --prod --dir=dist --auth={{secret:cloud.netlify.token}}"
    elif deploy_target == "docker":
        if "deploy" not in project_data:
            project_data["deploy"] = {}
        project_data["deploy"]["docker"] = f"docker build -t {project_id}:latest ."

    project_file.write_text(yaml.safe_dump(project_data), encoding="utf-8")

    # 5. Next Steps
    click.echo("\n🚀 Ready for liftoff!")
    click.echo("Run the following command to start the agent:")

    ssh_vol = ""
    if click.confirm("Do you use SSH for Git?", default=False):
        ssh_vol = "  -v ~/.ssh:/root/.ssh:ro \\\n"

    cmd = f"""
docker run -d \\
  --name blondie \\
  --restart always \\
  -v $(pwd):/workspace \\
  -v ~/.blondie/secrets.env.yaml:/workspace/.agent/secrets.env.yaml \\
{ssh_vol}  blondie:latest run
"""
    click.echo(cmd.strip())


def run_init_wizard() -> None:
    """Run the full initialization wizard."""
    secrets = setup_secrets()
    validate_secrets(secrets)
    setup_workspace()
    stack_detection()
    interview()
