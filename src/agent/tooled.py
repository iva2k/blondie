# src/llm/tooled.py

"""Tool execution handler for LLM sessions."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from agent.executor import CommandTimeoutError
from llm.client import LLMResponse
from llm.journal import Journal

if TYPE_CHECKING:
    from agent.context import ContextGatherer
    from agent.executor import Executor
    from agent.progress import ProgressManager
    from agent.project import Project
    from agent.router import ChatSession, LLMRouter
    from agent.tasks import TasksManager
    from cli import GitCLI


TOOL_DEFINITIONS = {
    "run_shell": {
        "name": "run_shell",
        "description": "Execute a shell command on the host machine."
        " Use for exploration (ls, grep, find) or limited execution.",
        "parameters": {
            "type": "object",
            "properties": {"command": {"type": "string", "description": "The shell command to execute."}},
            "required": ["command"],
        },
    },
    "read_file": {
        "name": "read_file",
        "description": "Read the contents of a file.",
        "parameters": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Path to the file relative to repo root."}},
            "required": ["path"],
        },
    },
    "write_file": {
        "name": "write_file",
        "description": "Write content to a file. Overwrites existing content.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file relative to repo root."},
                "content": {"type": "string", "description": "Full content to write to the file."},
            },
            "required": ["path", "content"],
        },
    },
    "find_package": {
        "name": "find_package",
        "description": "Find available versions for a package. Supported ecosystems: python (pypi), node (npm).",
        "parameters": {
            "type": "object",
            "properties": {
                "package_name": {"type": "string", "description": "Name of the package."},
                "ecosystem": {
                    "type": "string",
                    "enum": ["python", "node"],
                    "description": "The ecosystem to search in.",
                },
            },
            "required": ["package_name", "ecosystem"],
        },
    },
    "get_next_task": {
        "name": "get_next_task",
        "description": "Get the next high-priority task from the backlog.",
        "parameters": {"type": "object", "properties": {}},
    },
    "claim_task": {
        "name": "claim_task",
        "description": "Claim a task to start working on it. Creates a git branch.",
        "parameters": {
            "type": "object",
            "properties": {"task_id": {"type": "string", "description": "The ID of the task to claim."}},
            "required": ["task_id"],
        },
    },
    "complete_task": {
        "name": "complete_task",
        "description": "Mark a task as completed in TASKS.md.",
        "parameters": {
            "type": "object",
            "properties": {"task_id": {"type": "string", "description": "The ID of the task to complete."}},
            "required": ["task_id"],
        },
    },
    "git_checkout": {
        "name": "git_checkout",
        "description": "Checkout a git branch (creates it if it doesn't exist).",
        "parameters": {
            "type": "object",
            "properties": {"branch_name": {"type": "string", "description": "Name of the branch."}},
            "required": ["branch_name"],
        },
    },
    "git_commit": {
        "name": "git_commit",
        "description": "Stage all files and commit.",
        "parameters": {
            "type": "object",
            "properties": {"message": {"type": "string", "description": "Commit message."}},
            "required": ["message"],
        },
    },
    "git_push": {
        "name": "git_push",
        "description": "Push current branch to remote.",
        "parameters": {
            "type": "object",
            "properties": {
                "branch_name": {"type": "string", "description": "Branch to push (optional, defaults to current)."}
            },
            "required": [],
        },
    },
    "git_merge": {
        "name": "git_merge",
        "description": "Merge a branch into another.",
        "parameters": {
            "type": "object",
            "properties": {
                "source_branch": {"type": "string", "description": "Branch to merge from."},
                "target_branch": {"type": "string", "description": "Branch to merge into."},
            },
            "required": ["source_branch", "target_branch"],
        },
    },
    "run_tests": {
        "name": "run_tests",
        "description": "Run the project's test suite.",
        "parameters": {"type": "object", "properties": {}},
    },
    "check_daily_limit": {
        "name": "check_daily_limit",
        "description": "Check if the daily cost limit has been exceeded.",
        "parameters": {"type": "object", "properties": {}},
    },
}


class ToolHandler:
    """Handles execution of tools requested by LLM."""

    def __init__(
        self,
        repo_path: Path,
        project: Project,
        executor: Executor,
        journal: Journal,
        progress: ProgressManager,
        llm: LLMRouter,
        context_gatherer: ContextGatherer,
        tasks_manager: TasksManager,
        git: GitCLI,
    ):
        self.repo_path = repo_path
        self.project = project
        self.executor = executor
        self.journal = journal
        self.progress = progress
        self.llm = llm
        self.context_gatherer = context_gatherer
        self.tasks_manager = tasks_manager
        self.git = git
        self.tool_definitions = TOOL_DEFINITIONS.copy()
        self.tool_implementations: dict[str, Callable] = {
            "run_shell": self._run_shell,
            "read_file": self._read_file,
            "write_file": self._write_file,
            "find_package": self._find_package,
            "get_next_task": self._get_next_task,
            "claim_task": self._claim_task,
            "complete_task": self._complete_task,
            "git_checkout": self._git_checkout,
            "git_commit": self._git_commit,
            "git_push": self._git_push,
            "git_merge": self._git_merge,
            "run_tests": self._run_tests,
            "check_daily_limit": self._check_daily_limit,
        }

    def register(self, name: str, definition: dict, implementation: Callable):
        """Register a new dynamic tool."""
        if name in self.tool_definitions:
            self.journal.print(f"⚠️  Overwriting existing tool definition for '{name}'")
        if name in self.tool_implementations:
            self.journal.print(f"⚠️  Overwriting existing tool implementation for '{name}'")
        self.tool_definitions[name] = definition
        self.tool_implementations[name] = implementation

    async def _run_shell(self, command: str, cmd_instruction: str | None = None, **_kwargs) -> str:
        """Execute a shell command."""
        if not command:
            return "Error: Missing command argument"

        # Heuristic: map install commands to 'add-package' gate
        gate = "add-package" if any(x in command for x in ["install", "add", "npm", "pip", "poetry"]) else "shell"

        async def interaction_callback(cmd_input: str, stdout: str, stderr: str, _cmd_ctx=command) -> str:
            response = await self.llm.interact_with_shell(
                self.context_gatherer,
                instruction=cmd_instruction or "No instruction provided.",
                command=cmd_input,
                stdout=stdout,
                stderr=stderr,
            )
            return response.content.strip()

        # Use executor with high timeout for exploration
        try:
            res = await asyncio.wait_for(
                self.executor.run(command, gate=gate, interaction_callback=interaction_callback),
                timeout=120,
            )
        except CommandTimeoutError as e:
            res = e.result
        output = f"Exit Code: {res.returncode}\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
        status = "SUCCESS" if res.returncode == 0 else f"FAILED RC:{res.returncode}"
        self.progress.add_action("SHELL", command, status)
        return output

    async def _read_file(self, path: str, **_kwargs) -> str:
        """Read a file's contents."""
        if not path:
            return "Error: Missing path argument"

        full_path = (self.repo_path / path).resolve()
        # Security check: ensure inside repo
        if not full_path.is_relative_to(self.repo_path.resolve()):
            self.progress.add_action("READ", path, "FAILED: Access Denied")
            return f"Error: Access denied. Path {path} is outside repository."
        if full_path.relative_to(self.repo_path.resolve()).as_posix() in self.project.protected_files:
            self.progress.add_action("READ", path, "FAILED: Protected File")
            return f"Error: Access denied. File {path} is protected."
        if not full_path.exists():
            self.progress.add_action("READ", path, "FAILED: Not Found")
            return f"Error: File {path} not found."
        if full_path.is_dir():
            self.progress.add_action("READ", path, "FAILED: Is Directory")
            return f"Error: {path} is a directory."

        output = await asyncio.to_thread(full_path.read_text, encoding="utf-8")
        self.progress.add_action("READ", path, "SUCCESS")
        return output

    async def _write_file(self, path: str, content: str, **_kwargs) -> str:
        """Write content to a file."""
        if not path:
            return "Error: Missing path argument"

        full_path = (self.repo_path / path).resolve()
        # Security check: ensure inside repo
        if not full_path.is_relative_to(self.repo_path.resolve()):
            self.progress.add_action("WRITE", path, "FAILED: Access Denied")
            return f"Error: Access denied. Path {path} is outside repository."
        if full_path.relative_to(self.repo_path.resolve()).as_posix() in self.project.protected_files:
            self.progress.add_action("WRITE", path, "FAILED: Protected File")
            return f"Error: Access denied. File {path} is protected."
        if full_path.exists() and full_path.is_dir():
            self.progress.add_action("WRITE", path, "FAILED: Is Directory")
            return f"Error: {path} is a directory."

        # Ensure directory exists
        full_path.parent.mkdir(parents=True, exist_ok=True)

        # Write content (async to avoid blocking event loop)
        await asyncio.to_thread(full_path.write_text, content, encoding="utf-8")
        self.progress.add_action("WRITE", path, "SUCCESS")
        return f"Successfully wrote to {path}"

    async def _find_package(self, package_name: str, ecosystem: str, **_kwargs) -> str:
        """Find available package versions."""
        if not package_name or not ecosystem:
            return "Error: Missing package_name or ecosystem"

        cmd = ""
        if ecosystem == "python":
            cmd = f"pip index versions {package_name}"
        elif ecosystem == "node":
            cmd = f"npm view {package_name} versions"

        if not cmd:
            return f"Error: Unsupported ecosystem '{ecosystem}'"

        try:
            res = await asyncio.wait_for(self.executor.run(cmd, gate="shell"), timeout=30)
        except CommandTimeoutError as e:
            res = e.result
        if res.returncode == 0:
            output = res.stdout[:2000] + ("..." if len(res.stdout) > 2000 else "")
            self.progress.add_action("FIND_PKG", f"{ecosystem}:{package_name}", "SUCCESS")
        else:
            output = f"Error finding package: {res.stderr or res.stdout}"
            self.progress.add_action("FIND_PKG", f"{ecosystem}:{package_name}", "FAILED")
        return output

    async def _get_next_task(self, **_kwargs) -> str:
        """Get the next high-priority task."""
        task = await asyncio.to_thread(self.tasks_manager.get_next_task)
        if not task:
            return "No tasks available."
        return f"Task ID: {task.id}\nTitle: {task.title}\nPriority: {task.priority}"

    async def _claim_task(self, task_id: str, **_kwargs) -> str:
        """Claim a task."""
        if not task_id:
            return "Error: Missing task_id"

        try:
            success = await asyncio.to_thread(self.tasks_manager.claim_task, task_id, self.git)
            if success:
                self.progress.add_action("CLAIM_TASK", task_id, "SUCCESS")
                return f"Successfully claimed task {task_id}."
            else:
                self.progress.add_action("CLAIM_TASK", task_id, "FAILED")
                return f"Failed to claim task {task_id}. It might be already claimed or branch exists."
        except Exception as e:  # pylint: disable=broad-exception-caught
            return f"Error claiming task: {e}"

    async def _complete_task(self, task_id: str, **_kwargs) -> str:
        """Complete a task."""
        if not task_id:
            return "Error: Missing task_id"

        try:
            success = await asyncio.to_thread(self.tasks_manager.complete_task, task_id)
            if success:
                self.progress.add_action("COMPLETE_TASK", task_id, "SUCCESS")
                return f"Successfully completed task {task_id}."
            else:
                self.progress.add_action("COMPLETE_TASK", task_id, "FAILED")
                return f"Failed to complete task {task_id}. Task not found or update failed."
        except Exception as e:  # pylint: disable=broad-exception-caught
            return f"Error completing task: {e}"

    async def _git_checkout(self, branch_name: str, **_kwargs) -> str:
        """Checkout a git branch."""
        if not branch_name:
            return "Error: Missing branch_name"
        try:
            await asyncio.to_thread(self.git.checkout_branch, branch_name)
            self.progress.add_action("GIT_CHECKOUT", branch_name, "SUCCESS")
            return f"Checked out branch {branch_name}"
        except Exception as e:  # pylint: disable=broad-exception-caught
            return f"Error checking out branch: {e}"

    async def _git_commit(self, message: str, **_kwargs) -> str:
        """Commit changes."""
        if not message:
            return "Error: Missing message"
        try:
            await asyncio.to_thread(self.git.add_all)
            await asyncio.to_thread(self.git.commit, message)
            self.progress.add_action("GIT_COMMIT", message, "SUCCESS")
            return f"Committed with message: {message}"
        except Exception as e:  # pylint: disable=broad-exception-caught
            return f"Error committing: {e}"

    async def _git_push(self, branch_name: str | None = None, **_kwargs) -> str:
        """Push branch."""
        try:
            if not branch_name:
                branch_name = await asyncio.to_thread(self.git.current_branch)
            await asyncio.to_thread(self.git.push, branch_name)
            self.progress.add_action("GIT_PUSH", branch_name, "SUCCESS")
            return f"Pushed branch {branch_name}"
        except Exception as e:  # pylint: disable=broad-exception-caught
            return f"Error pushing: {e}"

    async def _git_merge(self, source_branch: str, target_branch: str, **_kwargs) -> str:
        """Merge branches."""
        if not source_branch or not target_branch:
            return "Error: Missing branch names"
        try:
            await asyncio.to_thread(self.git.checkout, target_branch)
            await asyncio.to_thread(self.git.pull, target_branch)
            await asyncio.to_thread(self.git.run, "merge", source_branch)
            self.progress.add_action("GIT_MERGE", f"{source_branch} -> {target_branch}", "SUCCESS")
            return f"Merged {source_branch} into {target_branch}"
        except Exception as e:  # pylint: disable=broad-exception-caught
            return f"Error merging: {e}"

    async def _run_tests(self, **_kwargs) -> str:
        """Run project tests."""
        try:
            res = await self.executor.run_tests()
            status = "SUCCESS" if res.returncode == 0 else f"FAILED RC:{res.returncode}"
            output = f"Exit Code: {res.returncode}\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
            self.progress.add_action("RUN_TESTS", "all", status)
            return output
        except Exception as e:  # pylint: disable=broad-exception-caught
            return f"Error running tests: {e}"

    async def _check_daily_limit(self, **_kwargs) -> str:
        """Check daily cost limit."""
        try:
            is_within_limit = await asyncio.to_thread(self.llm.check_daily_limit)
            return "WITHIN_LIMIT" if is_within_limit else "LIMIT_EXCEEDED"
        except Exception as e:  # pylint: disable=broad-exception-caught
            return f"Error checking limit: {e}"

    async def run_loop(self, session: ChatSession, initial_response: LLMResponse, cmd_instruction: str) -> LLMResponse:
        """Handle interactive tool execution loop."""
        response = initial_response
        max_cycles = 15

        for _ in range(max_cycles):
            if not response.tool_calls:
                break

            self.journal.print(f"🛠️  Processing {len(response.tool_calls)} tool calls...")

            for tool in response.tool_calls:
                fn_name = tool["function"]["name"]
                try:
                    args = json.loads(tool["function"]["arguments"])
                except json.JSONDecodeError as e:
                    session.add_tool_result(tool["id"], f"Error: Invalid JSON arguments - {e}")
                    continue

                tool_id = tool["id"]
                output = ""
                self.journal.print(f"🔧 Executing {fn_name}: {args}")

                implementation = self.tool_implementations.get(fn_name)
                if not implementation:
                    output = f"Error: Unknown tool '{fn_name}'"
                else:
                    try:
                        # Pass cmd_instruction for tools that might need it, others will ignore it via **_kwargs
                        output = await implementation(cmd_instruction=cmd_instruction, **args)
                    # pylint: disable-next=broad-exception-caught
                    except Exception as e:
                        output = f"Error executing tool: {e}"
                        self.progress.add_action("TOOL_ERROR", fn_name, f"FAILED: {e}")

                session.add_tool_result(tool_id, output)

            # Get next response from LLM
            response = await session.send()

        return response
