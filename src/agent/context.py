# src/agent/context.py

"""Context gathering module."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent.policy import Policy
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
        task: Task | None = None,
        command: str | None = None,
    ):
        self.repo_path = repo_path
        self.project = project
        self.policy = policy
        self.git = git
        self.gitignore = gitignore
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
    ) -> str:
        """Gather project context for LLM."""
        items_val = {
            "project": False,
            "policy": False,
            "cwd": False,
            "git": False,
            "files": False,
            "task": False,
            "command": False,
        }
        if items:
            items_val.update(items)
        items = items_val

        context = []
        # TODO: (when needed) Implement: if items["spec"]: ...
        if items["cwd"]:
            context.append(f"CWD: {self.repo_path.resolve()}")
        context.append("Temp dir: ./_tmp")

        if items["project"]:
            context.append(f"Project: {self.project.id}")
            if self.project.dev_env:
                context.append(f"Dev Environment: {self.project.dev_env}")
        if items["policy"]:
            context.append(f"Policy: {self.policy.model_dump()}")
            # context.append(f"Commands: {list(self.policy.commands.keys())}")
        if items["git"]:
            context.append(f"Current branch: {self.git.current_branch()}")
            context.append(f"Git status:\n{self.git.status()}")
        if items["files"]:
            context.append(f"Existing Files:\n{self._get_file_tree()}\n")
        if self.task and items["task"]:
            context.append(f"Task: {self.task.id} {self.task.title}")
        if self.command and items["command"]:
            context.append(f"\nCommand: {self.command}")
        return "\n".join(context)

    def _get_file_tree(self) -> str:
        """Generate list of repo files (excluding ignored)."""
        files = []

        for path in sorted(self.repo_path.rglob("*")):
            if not path.is_file():
                continue

            try:
                rel_path = path.relative_to(self.repo_path)
            except ValueError:
                continue

            if rel_path.as_posix() in self.project.protected_files:
                continue

            if self.gitignore.is_ignored(path):
                continue

            if any(
                part.startswith(".") and part not in [".agent", ".github", ".gitignore", ".dockerignore"]
                for part in rel_path.parts
            ):
                continue

            files.append(str(rel_path))

        return "\n".join(files)
