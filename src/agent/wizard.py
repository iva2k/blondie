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
from agent.tasks import Task, TasksManager, TaskStatus


def _get_workspace(target_dir: Path | None = None) -> Path:
    """Determine the workspace path."""
    if target_dir:
        return target_dir
    workspace = Path("/workspace")
    if not workspace.exists():
        workspace = Path.cwd()
    return workspace


def setup_secrets() -> dict[str, Any]:
    """Interactive secrets setup."""
    click.echo("\n🔑 Secrets Setup")

    # Path inside container (mapped from host ~/.blondie) or local home
    if os.environ.get("BLONDIE_SECRETS_DIR"):
        secrets_dir = Path(os.environ["BLONDIE_SECRETS_DIR"])
    else:
        click.echo("Where do you want to store secrets?")
        click.echo("  [1] Global (~/.blondie) - Shared across projects")
        click.echo("  [2] Project (./.agent)  - Portable / Easy to deploy")
        choice = click.prompt("Select storage", default="2", type=click.Choice(["1", "2"]))

        if choice == "2":
            secrets_dir = _get_workspace() / ".agent"
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

    # Determine providers to prompt for (based on template config if available)
    workspace = _get_workspace()
    llm_config_file = workspace / ".agent" / "llm_config.yaml"
    providers = ["openai", "anthropic", "groq"]  # Defaults if no config found

    if llm_config_file.exists():
        try:
            llm_config = yaml.safe_load(llm_config_file.read_text(encoding="utf-8")) or {}
            if "providers" in llm_config:
                providers = list(llm_config["providers"].keys())
        except Exception as e:  # pylint: disable=broad-exception-caught
            click.echo(f"Warning: Could not read llm_config.yaml: {e}")

    display_names = {"openai": "OpenAI", "anthropic": "Anthropic", "groq": "Groq"}

    for provider in providers:
        if not secrets["llm"].get(provider, {}).get("api_key"):
            label = f"{display_names.get(provider, provider.capitalize())} API Key"
            # Default to yes for OpenAI (usually primary), no for others
            default_confirm = provider == "openai"

            if click.confirm(f"Do you want to set up {label}?", default=default_confirm):
                key = click.prompt(label, hide_input=True)
                secrets["llm"][provider] = {"api_key": key}

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

    workspace = _get_workspace()

    llm_yaml_path = workspace / ".agent" / "llm.yaml"

    success = asyncio.run(fetch_and_save_models(secrets, llm_yaml_path, log_func=click.echo))

    if success:
        click.echo(f"✅ Model list saved to {llm_yaml_path}")
    else:
        click.echo("⚠️  Could not verify any API keys. Please check your secrets.")


def setup_workspace(target_dir: Path | None = None) -> None:
    """Initialize workspace with git and templates (Task 105)."""
    click.echo("\n🛠️  Workspace Setup")

    workspace = _get_workspace(target_dir)

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
    # Resolves to .../blondie/templates assuming src/agent/wizard.py location
    templates_root = Path(__file__).parents[2] / "templates"

    if not templates_root.exists():
        click.echo(f"⚠️  Templates root not found at {templates_root}. Skipping template copy.")
        return

    # Discover available templates
    available_templates = [d.name for d in templates_root.iterdir() if d.is_dir() and not d.name.startswith(".")]
    if not available_templates:
        click.echo(f"⚠️  No templates found in {templates_root}.")
        return

    # Default to 'basic' if available, otherwise first one
    default_template = "basic" if "basic" in available_templates else available_templates[0]

    click.echo("Select a template:")
    for i, name in enumerate(available_templates, 1):
        click.echo(f"  [{i}] {name}")

    choice_idx = click.prompt(
        "Template",
        default=str(available_templates.index(default_template) + 1),
        type=click.IntRange(1, len(available_templates)),
    )
    selected_template = available_templates[choice_idx - 1]

    template_dir = templates_root / selected_template

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
    workspace = _get_workspace(target_dir)

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
    workspace = _get_workspace(target_dir)

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

    # Load existing project data to preserve fields not prompted for
    if project_file.exists():
        project_data = yaml.safe_load(project_file.read_text(encoding="utf-8")) or {}

    default_id = project_data.get("id", workspace.name)
    project_id = click.prompt("Project ID", default=default_id)
    project_data["id"] = project_id
    if "name" not in project_data or project_data["name"] == "My New Project":
        project_data["name"] = project_id

    git_user = click.prompt("Bot Git Name", default=project_data.get("git_user", "Blondie Bot"))
    project_data["git_user"] = git_user

    # 3. Initial Tasks
    tasks_file = agent_dir / "TASKS.md"
    if tasks_file.exists():
        if click.confirm("Do you want to add initial tasks?", default=True):
            click.echo("Enter tasks to add to the backlog (leave empty to finish):")

            new_task_titles = []
            while True:
                task_input = click.prompt("Task", default="", show_default=False)
                if not task_input.strip():
                    break
                new_task_titles.append(task_input.strip())

            if new_task_titles:
                tasks_manager = TasksManager(tasks_file, project_id=project_id.upper())

                next_id = 1
                existing_ids = [int(t.id) for t in tasks_manager.tasks if t.id.isdigit()]
                if existing_ids:
                    next_id = max(existing_ids) + 1

                for title in new_task_titles:
                    task_id = f"{next_id:03d}"
                    new_task = Task(
                        id=task_id,
                        priority="P1",
                        title=title,
                        depends_on=[],
                        status=TaskStatus.TODO,
                        raw_line="",
                        project_id=project_id.upper(),
                    )
                    tasks_manager.tasks.append(new_task)
                    next_id += 1

                tasks_manager._save()  # pylint: disable=protected-access
                click.echo(f"✅ Added {len(new_task_titles)} tasks to TASKS.md")

    # 4. Model Provider
    llm_file = agent_dir / "llm_config.yaml"
    if llm_file.exists():
        llm_data = yaml.safe_load(llm_file.read_text(encoding="utf-8")) or {}
        available_providers = list(llm_data.get("providers", {}).keys())
        if not available_providers:
            available_providers = ["openai", "anthropic", "groq"]

        provider = click.prompt(
            "Primary AI Provider", default=available_providers[0], type=click.Choice(available_providers)
        )

        if "operations" not in llm_data:
            llm_data["operations"] = {}

        # Get default model from config or fallback
        provider_config = llm_data.get("providers", {}).get(provider, {})
        selected_model = provider_config.get("default_model", "gpt-4o")

        for op in ["planning", "coding", "debugging", "review", "execution"]:
            if op not in llm_data["operations"]:
                llm_data["operations"][op] = []
            # Ensure list
            if not isinstance(llm_data["operations"][op], list):
                llm_data["operations"][op] = []

            # Prepend selected provider
            llm_data["operations"][op].insert(0, {"provider": provider, "model": selected_model})

        llm_file.write_text(yaml.safe_dump(llm_data), encoding="utf-8")

    # 5. Deployment
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

    # Determine where secrets ended up to advise on next steps
    secrets_local = (agent_dir / "secrets.env.yaml").exists()

    # 5. Next Steps
    click.echo("\n🚀 Ready for liftoff!")

    if secrets_local:
        click.echo("\n[Deployment Transfer]")
        click.echo("Since secrets are in .agent/, you can deploy by copying this folder to your server:")
        click.echo(f"  scp -r {workspace.name}/ user@your-server:/path/to/projects/")
        click.echo("\nThen run this on the server:")
        secrets_mount = "-v $(pwd)/.agent/secrets.env.yaml:/workspace/.agent/secrets.env.yaml"
    else:
        click.echo("Run the following command to start the agent:")
        secrets_mount = "-v ~/.blondie/secrets.env.yaml:/workspace/.agent/secrets.env.yaml"

    ssh_vol = ""
    if click.confirm("Do you use SSH for Git?", default=False):
        ssh_vol = "  -v ~/.ssh:/root/.ssh:ro \\\n"

    cmd = f"""
docker run -d \\
  --name blondie \\
  --restart always \\
  -v $(pwd):/workspace \\
  {secrets_mount} \\
{ssh_vol}  blondie:latest run
"""
    click.echo(cmd.strip())


def run_init_wizard() -> None:
    """Run the full initialization wizard."""
    setup_workspace()
    stack_detection()
    # Run secrets setup after workspace so we can detect template providers
    secrets = setup_secrets()
    validate_secrets(secrets)
    interview()
