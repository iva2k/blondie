# src/agent/loop.py

"""Blondie main agent loop."""

import asyncio
import shutil
from pathlib import Path

import click
import yaml

from agent.executor import Executor
from agent.policy import Policy
from agent.project import Project
from agent.tasks import Task, TasksManager
from cli import GitCLI
from lib.gitignore import GitIgnore
from llm import Journal, LLMRouter


class BlondieAgent:
    """Main autonomous coding agent."""

    def __init__(self, repo_path: str, journal_dir: str | None = None):
        self.repo_path = Path(repo_path)
        self.agent_dir = self.repo_path / ".agent"
        self.project = Project.from_file(self.agent_dir / "project.yaml")
        self.journal = Journal(journal_dir, project_id=self.project.id)
        self.policy_path = self.agent_dir / self.project.policy
        self.policy = Policy.from_file(self.policy_path)
        self.tasks_path = self.agent_dir / "TASKS.md"
        self.secrets_path = self.agent_dir / "secrets.env.yaml"
        self.llm_config_path = self.agent_dir / "llm_config.yaml"

        self.tasks = TasksManager(self.tasks_path, project_id=self.project.id.upper(), journal=self.journal)
        self.git = GitCLI(self.repo_path, self.policy, self.journal)
        self.exec = Executor(self.repo_path, self.policy, self.journal)
        self.gitignore = GitIgnore(self.repo_path)
        self.llm = LLMRouter(self.secrets_path, self.llm_config_path, self.policy, self.journal)

    async def run_once(self) -> bool:
        """Execute one full task cycle. Returns True if task completed."""
        # 025: Check daily limit
        if not self.llm.check_daily_limit():
            return False

        # 0. Handle uncommitted changes from previous run/crash
        status = self.exec.run("git status --porcelain")
        if status.stdout.strip():
            self.journal.print("⚠️  Found uncommitted changes from previous session.")
            current_branch = self.git.current_branch()

            if current_branch == self.project.main_branch:
                self.journal.print("🧹 Stashing changes on main to allow pull...")
                _res = self.exec.run("git stash -u")
            else:
                self.journal.print(f"💾 Saving WIP on {current_branch}...")
                self._save_wip(current_branch, "WIP: Crash recovery")

        # 1. Sync with main branch to ensure fresh start
        main_branch = self.project.main_branch
        self.git.checkout(main_branch)
        self.git.pull(main_branch)

        # 2. Try to recover existing work
        task = self.tasks.recover_active_task(self.git)

        if task:
            self.journal.print(f"🔄 Recovered active task [bold cyan]{task.id}[/] {task.title}")
            self.journal.start_task(task.id)
        else:
            # 3. Pick next task
            task = self.tasks.get_next_task()
            if not task:
                self.journal.print("✅ No tasks left, exiting.")
                return False

            self.journal.print(f"\n🚀 Processing [bold cyan]{task.id}[/] {task.title}")
            self.journal.start_task(task.id)

            # 4. Claim task
            if not self.tasks.claim_task(task.id, self.git):
                self.journal.print(f'⚠️  Task {task.id} already claimed (remote branch "{task.branch_name}" exists)')
                return False

        branch_name = task.branch_name
        start_cost = self.llm.daily_cost

        try:
            # 1. Ensure we are on the branch (idempotent)
            self.git.checkout_branch(branch_name)

            # 2. LLM Implementation Plan
            context = self._gather_context(task)
            plan_response = await self.llm.plan_task(task.title, context, self.policy.model_dump())
            plan = plan_response.content
            self.journal.print(
                f"📋 [dim]Plan:[/dim]\n{plan}", truncate=500
            )  ## TODO: (now) decide if we want to print plan to the console

            # 3. LLM File Edits
            edit_result = await self._apply_llm_edits(task, plan)
            if not edit_result:
                self.journal.print("❌ LLM edits failed")
                self._save_wip(branch_name, f"WIP: {task.title} (Edits Failed)")
                return False

            # 4. Test Loop (with retries)
            max_retries = self.policy.limits.get("max_test_retries", 3)
            tests_passed = False

            for attempt in range(max_retries):
                test_result = self.exec.run_tests()
                if test_result.returncode == 0:
                    tests_passed = True
                    break

                self.journal.print(f"❌ Tests failed (Attempt {attempt + 1}/{max_retries})")
                if attempt == max_retries:
                    break

                self.journal.print("🔧 Triggering LLM debug...")
                context = self._gather_context(task)  # Refresh context
                debug_response = await self.llm.debug_error(task.title, test_result.stderr, context)
                fix_plan = debug_response.content
                self.journal.print(f"📋 [dim]Fix Plan:[/dim]\n{fix_plan}", truncate=500)

                if not await self._apply_llm_edits(task, fix_plan):
                    self.journal.print("❌ LLM fix edits failed")
                    self._save_wip(branch_name, f"WIP: {task.title} (Fix Edits Failed)")
                    return False

            if not tests_passed:
                self.journal.print(f"❌ Tests failed after {max_retries} retries - leaving task for manual review")
                self._save_wip(branch_name, f"WIP: {task.title} (Tests Failed)")
                return False

            # 5. Commit & Push
            self.git.add_all()
            self.git.commit(task.title)
            self.git.push(branch_name)
            self.journal.print(f"✅ Pushed [green]{branch_name}[/] 🎉")

            # 6. Complete task
            self.tasks.complete_task(task.id)

            # 7. Commit TASKS.md update & Merge
            self.git.add(self.tasks_path.relative_to(self.repo_path))
            self.git.commit(f"Complete task {task.id}")
            self.git.push(branch_name)

            if not self.git.merge_if_clean(branch_name, main_branch):
                self.journal.print("⚠️  Merge failed (conflicts?), leaving branch for manual review.")
                return True  # Task is technically done, just not merged

            self.journal.print(f"✅ Completed task [bold green]{task.full_id}[/]: {task.title}")
            self.journal.print(f"{'=' * 100}\n")
            return True

        except Exception as e:
            self.journal.print(f"💥 Task failed: {e}")
            self._save_wip(branch_name, f"WIP: Crash recovery - {e}")
            self.journal.print("Leaving task In Progress for review...")
            return False
        finally:
            # 042: Log task cost
            task_cost = self.llm.daily_cost - start_cost
            self.journal.print(f"💰 Task cost: ${task_cost:.4f}")

    def _save_wip(self, branch_name: str, message: str) -> None:
        """Save current work as WIP commit."""
        try:
            if self.git.current_branch() == branch_name:
                self.journal.print("💾 Saving WIP state...")
                self.git.add_all()
                self.git.commit(message)
                self.git.push(branch_name)
        except Exception as e:
            self.journal.print(f"⚠️ Failed to save WIP: {e}")

    def _gather_context(
        self,
        task: Task | None = None,
        include_project: bool = True,
        include_policy: bool = True,
        include_cwd: bool = False,
        include_git: bool = False,
        include_files: bool = True,
        include_task: bool = True,
        # TODO: (when needed) include_spec: bool = True,
    ) -> str:
        """Gather project context for LLM."""
        context = []
        if include_cwd:
            context.append(f"CWD: {self.repo_path.resolve()}")
        context.append("Temp dir: ./_tmp")

        if include_project:
            context.append(f"Project: {self.project.id}")
            if self.project.dev_env:
                context.append(f"Dev Environment: {self.project.dev_env}")
        if include_policy:
            context.append(f"Policy: {self.policy.model_dump()}")
            context.append(f"Commands: {list(self.policy.commands.keys())}")
        if include_git:
            context.append(f"Current branch: {self.git.current_branch()}")
            context.append(f"Git status:\n{self.git.status()}")
        if include_files:
            context.append(f"Existing Files:\n{self._get_file_tree()}\n")
        if task and include_task:
            context.append(f"Task: {task.id} {task.title}")
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

    async def _apply_llm_edits(self, task: Task, plan: str) -> bool:
        """Apply LLM-generated file edits."""
        self.journal.print("🤔 Identifying files to edit...")

        # Gather file structure context so the LLM knows valid paths
        context = self._gather_context(
            task,
            include_project=False,
            include_policy=False,
            include_files=True,
            include_task=False,
        )
        response = await self.llm.get_file_edits(task.title, plan, context=context)

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
                self.journal.print(f"❌ Expected list of edits, got {type(edits)}")
                return False
        except Exception as e:
            self.journal.print(f"❌ Failed to parse file edits: {e}")
            return False

        self.journal.print(f"📝 Found {len(edits)} file operations.")

        for edit in edits:
            action = edit.get("action", "edit")
            instruction = edit.get("instruction")

            if action == "shell":
                command = edit.get("command") or instruction
                timeout = int(edit.get("timeout", 120))
                if not command:
                    self.journal.print("⚠️  Missing command for shell action")
                    continue

                # Heuristic: map install commands to 'add-package' gate
                gate = (
                    "add-package" if any(x in command for x in ["install", "add", "npm", "pip", "poetry"]) else "shell"
                )

                max_retries = self.policy.limits.get("max_shell_retries", 3)
                cmd_success = False

                for attempt in range(max_retries):
                    result = self.exec.run(command, gate=gate, timeout=timeout)
                    if result.returncode == 0:
                        cmd_success = True
                        break

                    self.journal.print(f"❌ Shell command failed (Attempt {attempt + 1}/{max_retries})")
                    if attempt == max_retries:
                        break

                    self.journal.print("🔧 Triggering LLM debug for shell command...")
                    # Use full context in llm.debug_error
                    context = self._gather_context(task)  # Refresh context
                    context += f"\nCommand: {command}"
                    # TODO: (now) Ponder on splitting debug_error() into debug_test_error() and debug_shell_error() with specialization
                    debug_response = await self.llm.debug_error(
                        task.title, f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}", context
                    )
                    fix_plan = debug_response.content
                    self.journal.print(f"📋 [dim]Shell Fix Plan:[/dim]\n{fix_plan}", truncate=500)

                    if not await self._apply_llm_edits(task, fix_plan):
                        self.journal.print("❌ LLM fix edits failed, aborting retries.")
                        break

                if not cmd_success:
                    return False
                continue

            path_str = edit.get("path")
            if not path_str:
                continue

            full_path = self.repo_path / path_str

            # Check protected files
            try:
                resolved_path = full_path.resolve()
                resolved_repo = self.repo_path.resolve()
                if resolved_path.is_relative_to(resolved_repo):
                    rel_path = resolved_path.relative_to(resolved_repo)
                    if rel_path.as_posix() in self.project.protected_files:
                        self.journal.print(f"🛡️  Skipping protected file {path_str}")
                        continue
            except Exception:
                pass

            # Detect directory operation
            is_dir_op = path_str.endswith("/") or path_str.endswith("\\")

            if action == "delete":
                if full_path.exists():
                    if full_path.is_dir():
                        shutil.rmtree(full_path)
                        self.journal.print(f"🗑️  Deleted directory {path_str}...")
                    else:
                        self.journal.print(f"🗑️  Deleting {path_str}...")
                        full_path.unlink()
                else:
                    self.journal.print(f"⚠️  File to delete not found: {path_str}")
                continue

            # Handle directory creation
            if is_dir_op:
                if action == "create":
                    if full_path.exists() and not full_path.is_dir():
                        self.journal.print(f"⚠️  Removing file {path_str} to create directory.")
                        full_path.unlink()

                    if not full_path.exists():
                        self.journal.print(f"📂 Creating directory {path_str}...")
                        full_path.mkdir(parents=True, exist_ok=True)
                continue

            if not instruction:
                self.journal.print(f"⚠️  Missing instruction for {path_str}")
                continue

            verb = {"create": "Creating", "edit": "Editing"}.get(action, f"{action.title()}ing")
            self.journal.print(f"✍️  {verb} {path_str}...")

            # Ensure parent directory structure is valid (handle file-blocking-directory)
            p = full_path.parent
            while p != self.repo_path:
                if p.exists():
                    if not p.is_dir():
                        self.journal.print(f"⚠️  Removing file {p.relative_to(self.repo_path)} to create directory.")
                        p.unlink()
                        p.mkdir()
                    break
                p = p.parent

            # Ensure target is not a directory (handle directory-blocking-file)
            if full_path.is_dir():
                try:
                    full_path.rmdir()
                    self.journal.print(f"⚠️  Removed empty directory {path_str} to create file.")
                except OSError:
                    self.journal.print(f"❌ Directory {path_str} exists and is not empty. Cannot overwrite with file.")
                    continue

            existing_content = ""
            if full_path.exists():
                if action == "create":
                    self.journal.print(f"⚠️  File {path_str} already exists, treating as edit.")
                existing_content = full_path.read_text(encoding="utf-8")
            elif action == "edit":
                self.journal.print(f"⚠️  File {path_str} not found for edit, treating as create.")

            # Provide file list context for imports
            context = self._gather_context(
                task,
                include_project=False,
                include_policy=False,
                include_files=True,
                include_task=True,
            )
            code_resp = await self.llm.generate_code(
                task.title, path_str, existing_content, instruction, context=context
            )

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
        self.journal.print("🔄 Blondie agent loop started")
        completed = 0

        while True:
            # 025: Check daily limit
            if not self.llm.check_daily_limit():
                self.journal.print("⏳ Daily limit reached. Idling for 1 hour...")
                await asyncio.sleep(3600)
                continue

            try:
                success = await self.run_once()
                if success:
                    completed += 1

                # Brief pause between tasks
                await asyncio.sleep(2)

                # Exit if no tasks remain
                if not self.tasks.get_todo_tasks():
                    self.journal.print(f"🎉 All {completed} tasks completed!")
                    break

            except KeyboardInterrupt:
                self.journal.print("\n⏹️  Interrupted by user")
                break
            except Exception as e:
                self.journal.print(f"💥 Unexpected error: {e}")
                await asyncio.sleep(5)  # Brief pause on error

    async def run(self) -> None:
        """Run one cycle or forever based on config."""
        try:
            if self.project.mode == "once":
                await self.run_once()
            else:
                await self.run_forever()
        finally:
            # 043: Log daily cost on exit
            self.journal.print(f"💰 Total session cost: ${self.llm.daily_cost:.4f}")


async def main(repo_path: str, journal_dir: str | None = None) -> None:
    """CLI entry point."""
    agent = BlondieAgent(repo_path, journal_dir)
    await agent.run()


@click.command()
@click.argument("repo_path", default=".", type=click.Path(exists=True, file_okay=False, dir_okay=True))
@click.option(
    "--journal-dir",
    default=None,
    help="Directory to store journal logs",
    type=click.Path(file_okay=False, dir_okay=True),
)
def entry_point(repo_path: str = ".", journal_dir: str | None = None) -> None:
    """Blondie Agent CLI."""
    asyncio.run(main(repo_path, journal_dir))


if __name__ == "__main__":
    entry_point()
