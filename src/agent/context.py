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

    def gather(
        self,
        items: dict[str, bool] | None = None,
    ) -> tuple[str, dict[str, str]]:
        """Gather project context for LLM."""
        items = items or {}

        # Define order for the string output
        context_generators = {
            "cwd": self._get_cwd_context,
            "project": self._get_project_context,
            "policy": self._get_policy_context,
            "git": self._get_git_context,
            "files": self._get_files_context,
            "task": self._get_task_context,
            "command": self._get_command_context,
            "progress": self._get_progress_context,
            "env": self._get_env_context,
            "os": self._get_os_context,
        }

        context_parts: dict[str, str] = {}
        full_context: list[str] = []

        for key, getter in context_generators.items():
            if items.get(key, False):
                result = getter()
                if result:
                    if isinstance(result, str):
                        result = {key: result}
                    if isinstance(result, dict):
                        context_parts.update(result)
                        for k, v in result.items():
                            header = k.upper().replace("_", " ")
                            # if "\n" in v:
                            #     full_context.append(f"{header}:\n{v}")
                            # else:
                            #     full_context.append(f"{header}: {v}")
                            # Use Markdown-style headings:
                            full_context.append(f"\n### {header}\n\n{v}")

        # Reset context transient data
        self.command = None
        # self.task = None

        return "\n".join(full_context), context_parts

    def _get_cwd_context(self) -> dict[str, str] | str | None:
        return {
            "cwd": str(self.repo_path.resolve()),
            "Temp dir": "./_tmp",
        }

    def _get_project_context(self) -> dict[str, str] | str | None:
        return yaml.safe_dump(self.project.model_dump())

    def _get_policy_context(self) -> dict[str, str] | str | None:
        return yaml.safe_dump(self.policy.model_dump())

    def _get_git_context(self) -> dict[str, str] | str | None:
        return {
            "current_branch": self.git.current_branch(),
            "git_status": self.git.status(),
        }

    def _get_files_context(self) -> dict[str, str] | str | None:
        return self._get_file_tree()

    def _get_task_context(self) -> dict[str, str] | str | None:
        # return f"{self.task.id} {self.task.title}" if self.task else None
        # return yaml.safe_dump(self.task.model_dump(mode="json")) if self.task else None
        return (
            {
                "task_id": self.task.id,
                "task_priority": self.task.priority or "",
                "task_title": self.task.title,
                "task_full_id": self.task.full_id,
            }
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

    def _get_file_tree(self) -> dict[str, str] | str | None:
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
                part.startswith(".") and part not in [".git", ".github", ".dockerignore"] for part in rel_path.parts
            ):
                continue

            protected = ""
            if rel_path.as_posix() in self.project.protected_files:
                protected = " (* protected)"

            files.append(str(rel_path.as_posix()) + protected)

        return "\n".join(files)
