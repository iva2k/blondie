# src/agent/loop.py

"""Blondie main agent loop."""

import asyncio
import shutil
import traceback
from pathlib import Path

import yaml

from agent.context import ContextGatherer
from agent.executor import CommandTimeoutError, Executor
from agent.interaction import ConsoleInteractionProvider
from agent.policy import Policy
from agent.progress import ProgressManager
from agent.project import Project
from agent.router import LLMRouter
from agent.tasks import Task, TasksManager
from agent.tooled import ToolHandler
from cli import GitCLI
from lib.gitignore import GitIgnore
from llm import Journal


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
        self.progress_path = self.agent_dir / "progress.txt"

        self.tasks = TasksManager(self.tasks_path, project_id=self.project.id.upper(), journal=self.journal)
        self.git = GitCLI(self.repo_path, self.policy, self.journal, self.project.git_user, self.project.git_email)
        interactor = ConsoleInteractionProvider(self.journal)
        self.exec = Executor(self.repo_path, self.policy, self.project, self.journal, interactor)
        self.gitignore = GitIgnore(self.repo_path)
        self.progress = ProgressManager(self.progress_path)
        self.context_gatherer = ContextGatherer(
            self.repo_path,
            self.project,
            self.policy,
            self.git,
            self.gitignore,
            self.progress,
        )
        self.llm = LLMRouter(self.secrets_path, self.llm_config_path, self.policy, self.journal, progress=self.progress)
        self.tool_handler = ToolHandler(
            self.repo_path,
            self.project,
            self.exec,
            self.journal,
            self.progress,
            self.llm,
            self.context_gatherer,
            self.tasks,
            self.git,
        )

    async def _pick_task(self) -> Task | None:
        """Pick next task to run. Claims and starts the task."""

        # Check daily limit
        if not self.llm.check_daily_limit():
            return None

        # 0. Handle uncommitted changes from previous run/crash
        try:
            status = await asyncio.wait_for(self.exec.run("git status --porcelain"), timeout=120)
        except CommandTimeoutError as e:
            status = e.result
        if status.stdout.strip():
            self.journal.print("⚠️  Found uncommitted changes from previous session.")
            current_branch = self.git.current_branch()

            if current_branch == self.project.main_branch:
                self.journal.print("🧹 Stashing changes on main to allow pull...")
                try:
                    _res = await asyncio.wait_for(self.exec.run("git stash -u"), timeout=120)
                except CommandTimeoutError:
                    pass
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
                return None

            self.journal.print(f"\n🚀 Processing [bold cyan]{task.id}[/] {task.title}")
            self.journal.start_task(task.id)
            self.progress.clear()

            # 4. Claim task
            success, msg = self.tasks.claim_task(task.id, self.git)
            if not success:
                self.journal.print(f"⚠️  {msg}")
                return None

        return task

    async def run_once(self) -> bool:
        """Execute one full task cycle. Returns True if task completed."""

        # Check daily limit
        if not self.llm.check_daily_limit():
            return False

        task = await self._pick_task()
        if not task:
            return False

        branch_name = task.branch_name
        main_branch = self.project.main_branch
        start_cost = self.llm.daily_cost

        self.context_gatherer.add_task(task)

        try:
            # 1. Ensure we are on the branch (idempotent)
            self.git.checkout_branch(branch_name)

            # 2. LLM Implementation Plan
            session = self.llm.start_chat(
                "plan_task", self.context_gatherer, task_title=task.title, policy_summary=str(self.policy.model_dump())
            )
            plan_response = await session.send(prompt=session.user_content)
            plan_response = await self.tool_handler.run_loop(
                session, plan_response, cmd_instruction="Plan task tool calls"
            )
            plan = plan_response.content

            # self.journal.print(f"📋 [dim]Plan:[/dim]\n{plan}", truncate=500)

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
                test_result = await self.exec.run_tests()
                if test_result.returncode == 0:
                    tests_passed = True
                    break

                self.journal.print(f"❌ Tests failed (Attempt {attempt + 1}/{max_retries})")
                if attempt == max_retries:
                    break

                self.journal.print("🔧 Triggering LLM debug...")

                # Heuristic to improve agent success
                error_log = f"STDOUT:\n{test_result.stdout}\nSTDERR:\n{test_result.stderr}"
                debug_skill = "debug_error"
                # TODO: (when needed) debug_skill = "debug_native_crash"
                # if "access violation" in error_log or "segmentation fault" in error_log:
                #     debug_skill = "debug_native_crash"
                # elif "ModuleNotFoundError" in error_log:
                #     debug_skill = "debug_python_imports"

                session = self.llm.start_chat(
                    debug_skill,
                    self.context_gatherer,
                    task_title=task.title,
                    error_log=error_log,
                )
                debug_response = await session.send(prompt=session.user_content)
                debug_response = await self.tool_handler.run_loop(
                    session,
                    debug_response,
                    cmd_instruction=f"Debugging test failure\n"
                    f"STDOUT:\n{test_result.stdout}\n"
                    f"STDERR:\n{test_result.stderr}\n",
                )

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
            # Ensure progress.txt is added even if ignored (to keep it in task branch)
            try:
                self.git.add(self.progress_path.relative_to(self.repo_path), force=True)
            # pylint: disable-next=broad-exception-caught
            except Exception:
                pass

            self.git.commit(task.title)
            self.git.push(branch_name)
            self.journal.print(f"✅ Pushed [green]{branch_name}[/] 🎉")

            # 6. Complete task
            self.tasks.complete_task(task.id)

            # 7. Commit TASKS.md update & Merge
            self.git.add(self.tasks_path.relative_to(self.repo_path))
            self.git.commit(f"Complete task {task.id}")
            self.git.push(branch_name)

            exclude_files = [self.progress_path.relative_to(self.repo_path).as_posix()]
            if not self.git.merge_if_clean(branch_name, main_branch, exclude_files=exclude_files):
                self.journal.print("⚠️  Merge failed (conflicts?), leaving branch for manual review.")
                # TODO: (when needed) Implement LLM-assisted merge (due to conflicts when agents swarm merge changes to main)
                return True  # Task is technically done, just not merged

            self.journal.print(f"✅ Completed task [bold green]{task.full_id}[/]: {task.title}")
            self.journal.print(f"{'=' * 100}\n")
            return True

        # pylint: disable-next=broad-exception-caught
        except Exception as e:
            tb = traceback.format_exc()
            self.journal.print(f"💥 Task failed: {e}\n{tb}")
            self._save_wip(branch_name, f"WIP: Crash recovery - {e}")
            self.journal.print("Leaving task In Progress for review...")
            return False
        finally:
            # Archive progress log
            archive_path = self.journal.get_archive_path(".progress.txt")
            if archive_path:
                self.progress.archive(archive_path)

            # 042: Log task cost
            task_cost = self.llm.daily_cost - start_cost
            self.journal.print(f"💰 Task cost: ${task_cost:.4f}")

    def _save_wip(self, branch_name: str, message: str) -> None:
        """Save current work as WIP commit."""
        try:
            if self.git.current_branch() == branch_name:
                self.journal.print("💾 Saving WIP state...")
                self.git.add_all()
                if not self.git.is_clean():
                    self.git.commit(message)
                    self.git.push(branch_name)
                else:
                    self.journal.print("⚠️  Nothing to save (clean working directory)")
        # pylint: disable-next=broad-exception-caught
        except Exception as e:
            self.journal.print(f"⚠️ Failed to save WIP: {e}")

    def _create_interaction_callback(self, task: Task, instruction: str):
        """Create a callback for interactive shell commands."""

        async def callback(command: str, stdout: str, stderr: str) -> str:
            self.context_gatherer.add_task(task)
            self.journal.print(f"🤖 LLM Interaction for: {command}")
            response = await self.llm.interact_with_shell(
                self.context_gatherer, instruction=instruction, command=command, stdout=stdout, stderr=stderr
            )
            return response.content.strip()

        return callback

    async def _apply_llm_edits(self, task: Task, plan: str) -> bool:
        """Apply LLM-generated file edits."""
        self.journal.print("🤔 Identifying files to edit...")

        # Gather file structure context so the LLM knows valid paths
        self.context_gatherer.add_task(task)
        response = await self.llm.get_file_edits(self.context_gatherer, task.title, plan)

        if response.parsed:
            edits = [e.model_dump() for e in response.parsed.edits]
        else:
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
            # pylint: disable-next=broad-exception-caught
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

                gate = "shell"

                max_retries = self.policy.limits.get("max_shell_retries", 3)
                cmd_success = False

                for attempt in range(max_retries):
                    interaction = self._create_interaction_callback(task, instruction or command)
                    try:
                        result = await asyncio.wait_for(
                            self.exec.run(command, gate=gate, interaction_callback=interaction),
                            timeout=timeout,
                        )
                    except CommandTimeoutError as e:
                        result = e.result
                    if result.returncode == 0:
                        cmd_success = True
                        self.progress.add_action("SHELL", command + f" # timeout={timeout}", "SUCCESS")
                        break

                    self.journal.print(f"❌ Shell command failed (Attempt {attempt + 1}/{max_retries})")
                    self.progress.add_action(
                        "SHELL",
                        command + f" # timeout={timeout}",
                        f"FAILED RC:{result.returncode} STDOUT:{result.stdout} STDERR:{result.stderr}",
                    )
                    if attempt == max_retries:
                        break

                    self.journal.print("🔧 Triggering LLM debug for shell command...")
                    self.context_gatherer.add_task(task)
                    self.context_gatherer.add_command(command)
                    # TODO: (now) Ponder on splitting debug_error() into debug_test_error() and debug_shell_error() with specialization

                    session = self.llm.start_chat(
                        "debug_error",
                        self.context_gatherer,
                        task_title=task.title,
                        error_log=f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}",
                    )
                    debug_response = await session.send(prompt=session.user_content)
                    debug_response = await self.tool_handler.run_loop(
                        session,
                        debug_response,
                        cmd_instruction=instruction
                        or f"Debugging command `{command}` failure\n"
                        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}\n",
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
            # pylint: disable-next=broad-exception-caught
            except Exception:
                pass

            # Detect directory operation
            is_dir_op = path_str.endswith("/") or path_str.endswith("\\")

            if action == "delete":
                if full_path.exists():
                    if full_path.is_dir():
                        shutil.rmtree(full_path)
                        self.journal.print(f"🗑️  Deleted directory {path_str}...")
                        self.progress.add_action("DELETE_DIR", path_str)
                    else:
                        self.journal.print(f"🗑️  Deleting {path_str}...")
                        full_path.unlink()
                        self.progress.add_action("DELETE", path_str)
                else:
                    self.journal.print(f"⚠️  File to delete not found: {path_str}")
                continue

            # Handle directory creation
            if is_dir_op:
                if action == "create":
                    if full_path.exists() and not full_path.is_dir():
                        self.journal.print(f"⚠️  Removing file {path_str} to create directory.")
                        full_path.unlink()
                        self.progress.add_action("DELETE", full_path)

                    if not full_path.exists():
                        self.journal.print(f"📂 Creating directory {path_str}...")
                        full_path.mkdir(parents=True, exist_ok=True)
                        self.progress.add_action("CREATE_DIR", full_path)
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
                        self.progress.add_action("DELETE", p)
                    break
                p = p.parent

            # Ensure target is not a directory (handle directory-blocking-file)
            if full_path.is_dir():
                try:
                    full_path.rmdir()
                    self.journal.print(f"⚠️  Removed empty directory {path_str} to create file.")
                    self.progress.add_action("DELETE_DIR", full_path)
                except OSError:
                    self.journal.print(f"❌ Directory {path_str} exists and is not empty. Cannot overwrite with file.")
                    self.progress.add_action("DELETE_DIR", full_path)
                    continue

            existing_content = ""
            if full_path.exists():
                if action == "create":
                    self.journal.print(f"⚠️  File {path_str} already exists, treating as edit.")
                existing_content = full_path.read_text(encoding="utf-8")
            elif action == "edit":
                self.journal.print(f"⚠️  File {path_str} not found for edit, treating as create.")

            # Provide file list context for imports
            code_resp = await self.llm.generate_code(
                self.context_gatherer, task.title, path_str, existing_content, instruction
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
            self.progress.add_action(action.upper(), path_str + f" # {instruction}")

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
            # pylint: disable-next=broad-exception-caught
            except Exception as e:
                tb = traceback.format_exc()
                self.journal.print(f"💥 Unexpected error: {e}\n{tb}")
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
