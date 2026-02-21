"""Blondie main agent loop (bootstrap version)."""

import asyncio
from pathlib import Path

from .policy import Policy
from .project import Project


class BlondieAgent:
    """Main autonomous coding agent."""

    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)
        self.agent_dir = self.repo_path / ".agent"
        self.project = Project.from_file(self.agent_dir / "project.yaml")
        self.policy_path = self.agent_dir / self.project.policy
        self.policy = Policy.from_file(self.policy_path)

    async def run(self) -> None:
        """Main agent loop - claim tasks and execute."""
        print("🚀 Blondie bootstrap mode - policy loaded")
        print(f"   git-merge policy: {self.policy.check_permission('git-merge')}")

        # Simulate task loop
        for task_id in ["BLONDIE-001", "BLONDIE-002"]:
            print(f"Processing task {task_id}...")
            if self.policy.check_permission("git-checkout") == "allow":
                print(f"  ✓ Would checkout task-{task_id}")
            await asyncio.sleep(0.1)

    async def select_next_task(self) -> str | None:
        """Find next available task from TASKS.md."""
        tasks_md = self.agent_dir / self.project.task_source
        if not tasks_md.exists():
            return None
        # TODO: BLONDIE-002 use tasks.py
        return "BLONDIE-001"


async def main() -> None:
    """Entry point for bootstrap testing."""
    agent = BlondieAgent(".")
    await agent.run()


if __name__ == "__main__":
    asyncio.run(main())
