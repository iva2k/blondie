# src/agent/context.py

"""Context gathering module."""

from __future__ import annotations

import os
import platform
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    from agent.policy import Policy
    from agent.progress import ProgressManager
    from agent.project import Project
    from agent.tasks import Task
    from cli.git import GitCLI
    from lib.gitignore import GitIgnore


class ContextGatherer:
    """Gathers context for LLM prompts."""

    def __init__(
        self,
        repo_path: Path,
        project: Project,
        policy: Policy,
        git: GitCLI,
        gitignore: GitIgnore,
        progress: ProgressManager,
        task: Task | None = None,
        command: str | None = None,
    ):
        self.repo_path = repo_path
        self.project = project
        self.policy = policy
        self.git = git
        self.gitignore = gitignore
        self.progress = progress
        self.task = task
        self.command = command

    def add_task(self, task: Task | None):
        """Add task to context."""
        self.task = task

    def add_command(self, command: str):
        """Add command to context."""
        self.command = command

    def refresh(self) -> None:
        """Refresh context state (e.g. clear caches)."""
        # Currently no explicit caching is implemented in gather(), but this is the hook for it.
        # Future optimization: clear file tree cache here.

    def gather(
        self,
        items: dict[str, bool] | None = None,
        user_args: list[str] | None = None,
    ) -> tuple[str, dict[str, str]]:
        """Gather project context for LLM."""
        items = items or {}
        user_args = user_args or []

        # Define order for the string output
        context_generators = {
            "command": self._get_command_context,
            "cwd": self._get_cwd_context,
            "env": self._get_env_context,
            "files": self._get_files_context,
            "git": self._get_git_context,
            "os": self._get_os_context,
            "policy": self._get_policy_context,
            "progress": self._get_progress_context,
            "project": self._get_project_context,
            "task": self._get_task_context,
        }

        context_parts: dict[str, str] = {}
        full_context: list[str] = []
        guide_lines: list[str] = []

        descriptions = {
            # System prompt args:
            "arch": "The current hardware environment.",  # from "os" context
            "command": "The shell command that produced the error.",
            "cwd": "Current working directory.",
            "env": "Development environment guidelines.",
            "files": "The list of existing files in the repository.",
            "git": "Current git status and branch.",
            "instruction": "The specific change or implementation detail requested.",
            "os": "The current operating system environment.",
            "policy": "The agent's autonomy rules and allowed actions.",
            "progress": "History of previous attempts and actions on this task with their outcome.",
            "project": "Project configuration, languages, coding standards, and development guidelines.",
            "shell": "The current shell environment.",  # from "os" context
            "stderr": "The standard error captured so far.",
            "stdout": "The standard output captured so far.",
            "task": "The current sprint task id, title, priority, and description.",
            "temp_dir": "Temporary directory.",  # from "cwd" context
            # "task" fields:
            "task_id": "The current sprint task id. Use `task_id` for tool calls.",
            "priority": "The current sprint task priority.",
            "title": "The current sprint task title.",
            "full_id": "The current sprint task string. Use full_id for labeling the task in logs and commits.",
            # User prompt args:
            "error_log": "The error log or failure message to be analyzed.",
            "existing_content": "The current content of the file (if it exists).",
            "filename": "The path of the file to generate or edit.",
            "task_title": "The title of the task to be performed.",  # Rarely used
            "user_plan": "The high-level plan generated in the previous step.",
        }

        for key, getter in context_generators.items():
            result = getter()
            if result:
                if isinstance(result, str):
                    result = {key: result}
                if isinstance(result, dict):
                    context_parts.update(result)
                    for k, v in result.items():
                        header = k.upper().replace(" ", "_")
                        full_context.append(f"\n### [{header}]\n\n{v}")
                        desc = descriptions.get(header.lower(), f"{k.replace('_', ' ')} context.")
                        guide_lines.append(f"- `[{header}]`: {desc}")

        if user_args:
            guide_lines.append("\nYou are also provided with these inputs in the user prompt:")
            for k in user_args:
                header = k.upper().replace(" ", "_")
                desc = descriptions.get(header.lower(), f"User input: {k.replace('_', ' ')}")
                guide_lines.append(f"- `[{header}]`: {desc}")

        # Reset context transient data
        self.command = None
        # self.task = None

        guide = "## CONTEXT GUIDE\n\nYou are provided with these context sections:\n\n" + "\n".join(guide_lines) + "\n"
        return guide + "## CONTEXT\n\n" + "\n".join(full_context), context_parts

    def _get_cwd_context(self) -> dict[str, str] | str | None:
        return {
            "cwd": str(self.repo_path.resolve()),
            "temp_dir": "./_tmp",  # TODO: (when needed) parameter?
        }

    def _get_project_context(self) -> dict[str, str] | str | None:
        return yaml.safe_dump(self.project.model_dump())

    def _get_policy_context(self) -> dict[str, str] | str | None:
        return yaml.safe_dump(self.policy.model_dump())

    def _get_git_context(self) -> dict[str, str] | str | None:
        return {"git": f"Branch: {self.git.current_branch()}\nStatus:\n{self.git.status()}"}

    def _get_task_context(self) -> dict[str, str] | str | None:
        # return f"{self.task.id} {self.task.title}" if self.task else None
        return (
            yaml.safe_dump(
                {
                    "task_id": self.task.id,
                    "priority": self.task.priority or "",
                    "title": self.task.title,
                    "full_id": self.task.full_id,
                }
            )
            if self.task
            else None
        )

    def _get_command_context(self) -> dict[str, str] | str | None:
        return self.command

    def _get_progress_context(self) -> dict[str, str] | str | None:
        return self.progress.read() or "(None)"  # Return non-empty string to ensure context section is not empty

    def _get_env_context(self) -> dict[str, str] | str | None:
        if not self.project.dev_env:
            return None
        # TODO: (when needed) Implement whole dev_env, including environment
        # return yaml.safe_dump(self.project.dev_env.model_dump())
        guidelines = self.project.dev_env.get("guidelines", None) if self.project.dev_env else []
        if not guidelines:
            return None
        return "\n".join(f"- {g}" for g in guidelines)

    def _get_os_context(self) -> dict[str, str] | str | None:
        system = platform.system()
        release = platform.release()
        version = platform.version()
        machine = platform.machine()
        processor = platform.processor()

        os_info = f"{system} {release} ({version})"
        arch = f"{machine} ({processor})" if processor else machine

        if system == "Windows":
            if os.environ.get("MSYSTEM"):
                shell_info = f"Git Bash / MSYS2 ({os.environ.get('MSYSTEM')})"
            elif os.environ.get("SHELL"):
                shell_info = os.environ.get("SHELL", "")
            elif "PROMPT" in os.environ:
                shell_info = "cmd.exe"
            else:
                shell_info = "PowerShell"
        elif system == "Linux":
            if "microsoft" in release.lower() or "wsl" in release.lower():
                shell_info = "WSL bash"
            else:
                shell_info = os.environ.get("SHELL", "bash")
        elif system == "Darwin":
            shell_info = os.environ.get("SHELL", "zsh")
        else:
            shell_info = os.environ.get("SHELL", "Unknown")
        shell_info = shell_info or "Unknown"

        return {
            "os": str(os_info),
            "arch": str(arch),
            "shell": str(shell_info),
        }

    def _get_files_context(self) -> dict[str, str] | str | None:
        """Generate list of repo files (excluding ignored)."""
        files = []

        for path in sorted(self.repo_path.rglob("*")):
            if not path.is_file():
                continue

            try:
                rel_path = path.relative_to(self.repo_path)
            except ValueError:
                continue

            if self.gitignore.is_ignored(path):
                continue

            if any(
                part.startswith(".") and part not in [".git", ".github", ".dockerignore", ".gitignore"]
                for part in rel_path.parts
            ):
                continue

            protected = ""
            if rel_path.as_posix() in self.project.protected_files:
                protected = " (* protected)"

            files.append(str(rel_path.as_posix()) + protected)

        return "\n".join(files)
