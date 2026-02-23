# src/agent/loop.py

"""Blondie main agent loop."""

import asyncio
from pathlib import Path
import shutil

import click
import yaml
from rich.console import Console

from agent.executor import Executor
from agent.policy import Policy
from agent.project import Project  # Added per your edits
from agent.tasks import Task, TasksManager
from cli import GitCLI
from llm import LLMRouter

console = Console()


class BlondieAgent:
    """Main autonomous coding agent."""

    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)
        self.agent_dir = self.repo_path / ".agent"
        self.project = Project.from_file(self.agent_dir / "project.yaml")
        self.policy_path = self.agent_dir / self.project.policy
        self.policy = Policy.from_file(self.policy_path)
        self.tasks_path = self.agent_dir / "TASKS.md"
        self.secrets_path = self.agent_dir / "secrets.env.yaml"
        self.llm_config_path = self.agent_dir / "llm_config.yaml"

        self.tasks = TasksManager(self.tasks_path, project_id=self.project.id.upper())
        self.git = GitCLI(self.repo_path, self.policy)
        self.exec = Executor(self.repo_path, self.policy)
        self.llm = LLMRouter(self.secrets_path, self.llm_config_path, self.policy)

    async def run_once(self) -> bool:
        """Execute one full task cycle. Returns True if task completed."""
        # 1. Try to recover existing work
        task = self.tasks.recover_active_task(self.git)

        if task:
            console.print(f"🔄 Recovered active task [bold cyan]{task.id}[/] {task.title}")
        else:
            # 2. Pick next task
            task = self.tasks.get_next_task()
            if not task:
                console.print("✅ No tasks left, exiting.")
                return False

            console.print(f"\n🚀 Processing [bold cyan]{task.id}[/] {task.title}")

            # 3. Claim task
            if not self.tasks.claim_task(task.id, self.git):
                console.print(
                    f'⚠️  Task {task.id} already claimed (remote branch "{task.branch_name}" exists)'
                )
                return False

        branch_name = task.branch_name

        try:
            # 1. Ensure we are on the branch (idempotent)
            self.git.checkout_branch(branch_name)

            # 2. LLM Implementation Plan
            context = self._gather_context(task)
            plan_response = await self.llm.plan_task(task.title, context, self.policy.model_dump())
            plan = plan_response.content
            console.print(f"📋 [dim]Plan:[/dim]\n{plan[:500]}...")

            # 3. LLM File Edits (STUB - implement file editing)
            edit_result = await self._apply_llm_edits(task, plan)
            if not edit_result:
                console.print("❌ LLM edits failed")
                return False

            # 4. Test Loop (with retries)
            test_result = self.exec.run_tests()
            if test_result.returncode != 0:
                console.print("❌ Tests failed - triggering LLM debug")
                debug_response = await self.llm.debug_error(test_result.stderr, context)
                console.print(
                    f"🔧 [dim]LLM debug suggestion:[/dim]\n{debug_response.content[:300]}..."
                )
                # For v1: leave In Progress for manual fix
                return False

            # 5. Commit & Push
            self.git.add_all()
            self.git.commit(task.title)
            self.git.push(branch_name)
            console.print(f"✅ Pushed [green]{branch_name}[/] 🎉")

            # 6. Complete task
            self.tasks.complete_task(task.id)
            console.print(f"✅ Completed [bold green]{task.id}[/]!")
            return True

        except Exception as e:
            console.print(f"💥 Task failed: {e}")
            console.print("Leaving task In Progress for review...")
            return False

    def _gather_context(self, _task: Task) -> str:
        """Gather repo context for LLM."""
        context = []
        context.append(f"Repo: {self.project.id}")
        context.append(f"Policy: {self.policy.model_dump()}")
        context.append(f"Commands: {list(self.policy.commands.keys())}")
        context.append(f"Current branch: {self.git.current_branch()}")
        context.append(f"Git status:\n{self.git.status()}")
        context.append(f"Files:\n{self._get_file_tree()}")
        return "\n".join(context)

    def _get_file_tree(self) -> str:
        """Generate list of repo files (excluding ignored)."""
        files = []
        ignore_dirs = {
            ".git",
            "__pycache__",
            "node_modules",
            "dist",
            "build",
            ".mypy_cache",
            ".pytest_cache",
            ".venv",
            "venv",
            "coverage",
        }
        # TODO: (now) Use .gitignore instead of hard-coded list.

        for path in sorted(self.repo_path.rglob("*")):
            if not path.is_file():
                continue

            try:
                rel_path = path.relative_to(self.repo_path)
            except ValueError:
                continue

            if any(part in ignore_dirs for part in rel_path.parts):
                continue

            if any(
                part.startswith(".")
                and part not in [".agent", ".github", ".gitignore", ".dockerignore"]
                for part in rel_path.parts
            ):
                continue

            files.append(str(rel_path))

        return "\n".join(files)

    async def _apply_llm_edits(self, task: Task, plan: str) -> bool:
        """Apply LLM-generated file edits."""
        console.print("🤔 Identifying files to edit...")

        response = await self.llm.get_file_edits(task.title, plan)

        # Clean up potential markdown fences
        content = response.content.strip()
        if content.startswith("```"):
            lines = content.splitlines()
            lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            content = "\n".join(lines)

        try:
            edits = yaml.safe_load(content)
            if not isinstance(edits, list):
                console.print(f"❌ Expected list of edits, got {type(edits)}")
                return False
        except Exception as e:
            console.print(f"❌ Failed to parse file edits: {e}")
            return False

        console.print(f"📝 Found {len(edits)} file operations.")

        for edit in edits:
            path_str = edit.get("path")
            action = edit.get("action", "edit")
            instruction = edit.get("instruction")

            if not path_str:
                continue

            full_path = self.repo_path / path_str

            # Detect directory operation
            is_dir_op = path_str.endswith("/") or path_str.endswith("\\")

            if action == "delete":
                if full_path.exists():
                    if full_path.is_dir():
                        shutil.rmtree(full_path)
                        console.print(f"🗑️  Deleted directory {path_str}...")
                    else:
                        console.print(f"🗑️  Deleting {path_str}...")
                        full_path.unlink()
                else:
                    console.print(f"⚠️  File to delete not found: {path_str}")
                continue

            # Handle directory creation
            if is_dir_op:
                if action == "create":
                    if full_path.exists() and not full_path.is_dir():
                        console.print(f"⚠️  Removing file {path_str} to create directory.")
                        full_path.unlink()

                    if not full_path.exists():
                        console.print(f"📂 Creating directory {path_str}...")
                        full_path.mkdir(parents=True, exist_ok=True)
                continue

            if not instruction:
                console.print(f"⚠️  Missing instruction for {path_str}")
                continue

            console.print(f"✍️  {action.title()}ing {path_str}...")  ## TODO: (now) this logs silly verbs like "Createing" - change to a dict based conversion

            # Ensure parent directory structure is valid (handle file-blocking-directory)
            p = full_path.parent
            while p != self.repo_path:
                if p.exists():
                    if not p.is_dir():
                        console.print(f"⚠️  Removing file {p.relative_to(self.repo_path)} to create directory.")
                        p.unlink()
                        p.mkdir()
                    break
                p = p.parent

            # Ensure target is not a directory (handle directory-blocking-file)
            if full_path.is_dir():
                try:
                    full_path.rmdir()
                    console.print(f"⚠️  Removed empty directory {path_str} to create file.")
                except OSError:
                    console.print(f"❌ Directory {path_str} exists and is not empty. Cannot overwrite with file.")
                    continue

            existing_content = ""
            if full_path.exists():
                if action == "create":
                    console.print(f"⚠️  File {path_str} already exists, treating as edit.")
                existing_content = full_path.read_text(encoding="utf-8")
            elif action == "edit":
                console.print(f"⚠️  File {path_str} not found for edit, treating as create.")

            code_resp = await self.llm.generate_code(path_str, existing_content, instruction)

            # Clean up potential markdown fences for code
            code = code_resp.content.strip()
            if code.startswith("```"):
                lines = code.splitlines()
                lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                code = "\n".join(lines)

            # Ensure directory exists
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(code, encoding="utf-8")

        return True

    async def run_forever(self) -> None:
        """Run continuous task loop."""
        console.print("🔄 Blondie agent loop started")
        completed = 0

        while True:
            try:
                success = await self.run_once()
                if success:
                    completed += 1

                # Brief pause between tasks
                await asyncio.sleep(2)

                # Exit if no tasks remain
                if not self.tasks.get_todo_tasks():
                    console.print(f"🎉 All {completed} tasks completed!")
                    break

            except KeyboardInterrupt:
                console.print("\n⏹️  Interrupted by user")
                break
            except Exception as e:
                console.print(f"💥 Unexpected error: {e}")
                await asyncio.sleep(5)  # Brief pause on error

    async def run(self) -> None:
        """Run one cycle or forever based on config."""
        if self.project.mode == "once":
            await self.run_once()
        else:
            await self.run_forever()


async def main(repo_path: str) -> None:
    """CLI entry point."""
    agent = BlondieAgent(repo_path)
    await agent.run()


@click.command()
@click.argument(
    "repo_path", default=".", type=click.Path(exists=True, file_okay=False, dir_okay=True)
)
def entry_point(repo_path: str = ".") -> None:
    """Blondie Agent CLI."""
    asyncio.run(main(repo_path))


if __name__ == "__main__":
    entry_point()
