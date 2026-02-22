# src/agent/loop.py

"""Blondie main agent loop."""

import asyncio
from pathlib import Path

import click
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

        self.tasks = TasksManager(
            self.tasks_path, project_id=self.project.id.upper())
        self.git = GitCLI(self.repo_path, self.policy)
        self.exec = Executor(self.repo_path, self.policy)
        self.llm = LLMRouter(self.secrets_path, self.policy)

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
                    f"⚠️  Task {task.id} already claimed (remote branch \"{task.branch_name}\" exists)")
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
                    f"🔧 [dim]LLM debug suggestion:[/dim]\n{debug_response.content[:300]}...")
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
        return "\n".join(context)

    async def _apply_llm_edits(self, task: Task, plan: str) -> bool:
        """Apply LLM-generated file edits (STUB for v1)."""
        console.print("✨ [dim]LLM would edit files here (STUB)[/dim]")
        console.print(f"[dim]Simulating implementation of: {task.title}[/dim]")

        # v1 STUB: Create placeholder files or skip
        # TODO: BLONDIE-010 - Real file editing via LLM
        (self.repo_path / f"{task.id}.md").write_text(
            f"# Task {task.id}\n\nPlan:\n{plan}\n\nTODO: LLM implementation"
        )
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
@click.argument("repo_path", default=".", type=click.Path(exists=True, file_okay=False, dir_okay=True))
def entry_point(repo_path: str = ".") -> None:
    """Blondie Agent CLI."""
    asyncio.run(main(repo_path))


if __name__ == "__main__":
    entry_point()
