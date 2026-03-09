# src/agent/loop2.py

"""Blondie v2 Orchestrator Loop."""

import traceback
from pathlib import Path

from agent.context import ContextGatherer
from agent.executor import Executor
from agent.interaction import ConsoleInteractionProvider
from agent.policy import Policy
from agent.progress import ProgressManager
from agent.project import Project
from agent.router import LLMRouter
from agent.tasks import TasksManager
from agent.tooled import ToolHandler
from cli import GitCLI
from lib.gitignore import GitIgnore
from llm.journal import Journal


class BlondieOrchestrator:
    """v2 Recursive Orchestrator Agent."""

    def __init__(self, repo_path: str, journal_dir: str | None = None):
        self.repo_path = Path(repo_path)
        self.agent_dir = self.repo_path / ".agent"

        # Load configuration
        self.project = Project.from_file(self.agent_dir / "project.yaml")
        self.journal = Journal(journal_dir, project_id=self.project.id)
        self.policy = Policy.from_file(self.agent_dir / self.project.policy)
        self.secrets_path = self.agent_dir / "secrets.env.yaml"
        self.llm_config_path = self.agent_dir / "llm_config.yaml"

        # Initialize components
        self.tasks = TasksManager(self.agent_dir / "TASKS.md", project_id=self.project.id.upper(), journal=self.journal)
        self.git = GitCLI(self.repo_path, self.policy, self.journal, self.project.git_user, self.project.git_email)
        self.interactor = ConsoleInteractionProvider(self.journal)
        self.exec = Executor(self.repo_path, self.policy, self.project, self.journal, self.interactor)
        self.gitignore = GitIgnore(self.repo_path)
        self.progress = ProgressManager(self.agent_dir / "progress.txt")

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

        # Register v2 skills as tools to enable recursive execution
        self.llm.register_skills(self.tool_handler, self.context_gatherer)

    async def run(self) -> None:
        """Start the orchestrator loop."""
        self.progress.add_action("AGENT_START", "Orchestrator", "INFO")
        self.journal.start_task("orchestrator")
        self.journal.print("🚀 Starting Blondie Orchestrator...")

        try:
            # Initialize the root session with the orchestrator skill
            # Note: 'orchestrator' skill must exist (Task 064)
            session = self.llm.start_chat("coding_orchestrator", self.context_gatherer)
            response = await session.send(prompt=session.user_content)

            # Enter the tool execution loop
            # The orchestrator will call tools (get_next_task, plan_task, etc.)
            # The ToolHandler will execute them and return results to the LLM
            await self.tool_handler.run_loop(session, response, "Orchestrator")

            self.progress.add_llm_event(
                "LLM_SESSION",
                "orchestrator",
                session.skill.operation if session.skill else "orchestration",
                session.provider_name,
                session.model,
                "COMPLETED",
            )

            self.journal.print("🏁 Orchestrator session ended.")

        except KeyboardInterrupt:
            self.journal.print("\n⏹️  Interrupted by user")
            self.progress.add_action("AGENT_STOP", "Interrupted by user", "WARN")
        except Exception as e:  # pylint: disable=broad-exception-caught
            tb = traceback.format_exc()
            self.journal.print(f"💥 Orchestrator crashed: {e}\n{tb}")
            self.progress.add_action("AGENT_CRASH", str(e), "ERROR")
        finally:
            self.journal.print(f"💰 Total session cost: ${self.llm.daily_cost:.4f}")
            self.progress.add_action("AGENT_END", f"Cost: ${self.llm.daily_cost:.4f}", "INFO")
            await self.llm.close()
