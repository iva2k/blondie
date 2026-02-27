# src/llm/tooled.py

"""Tool execution handler for LLM sessions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from llm.client import LLMResponse
from llm.journal import Journal

if TYPE_CHECKING:
    from agent.executor import Executor
    from agent.progress import ProgressManager
    from agent.project import Project
    from llm.router import ChatSession


TOOL_DEFINITIONS = {
    "run_shell": {
        "name": "run_shell",
        "description": "Execute a shell command on the host machine. Use for exploration (ls, grep, find) or execution.",
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
    ):
        self.repo_path = repo_path
        self.project = project
        self.executor = executor
        self.journal = journal
        self.progress = progress

    async def run_loop(self, session: ChatSession, initial_response: LLMResponse) -> LLMResponse:
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
                except json.JSONDecodeError:
                    session.add_tool_result(tool["id"], "Error: Invalid JSON arguments")
                    continue

                tool_id = tool["id"]
                output = ""

                self.journal.print(f"🔧 Executing {fn_name}: {args}")

                try:
                    if fn_name == "run_shell":
                        command = args.get("command")
                        if not command:
                            output = "Error: Missing command argument"
                        else:
                            # Heuristic: map install commands to 'add-package' gate
                            gate = (
                                "add-package"
                                if any(x in command for x in ["install", "add", "npm", "pip", "poetry"])
                                else "shell"
                            )
                            # Use executor with high timeout for exploration
                            res = self.executor.run(command, gate=gate, timeout=120)
                            output = f"Exit Code: {res.returncode}\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
                            status = "SUCCESS" if res.returncode == 0 else f"FAILED RC:{res.returncode}"
                            self.progress.add_action("SHELL", command, status)

                    elif fn_name == "read_file":
                        path_str = args.get("path")
                        if not path_str:
                            output = "Error: Missing path argument"
                        else:
                            full_path = (self.repo_path / path_str).resolve()
                            # Security check: ensure inside repo
                            if not full_path.is_relative_to(self.repo_path.resolve()):
                                output = f"Error: Access denied. Path {path_str} is outside repository."
                                self.progress.add_action("READ", path_str, "FAILED: Access Denied")
                            elif (
                                full_path.relative_to(self.repo_path.resolve()).as_posix()
                                in self.project.protected_files
                            ):
                                output = f"Error: Access denied. File {path_str} is protected."
                                self.progress.add_action("READ", path_str, "FAILED: Protected File")
                            elif not full_path.exists():
                                output = f"Error: File {path_str} not found."
                                self.progress.add_action("READ", path_str, "FAILED: Not Found")
                            elif full_path.is_dir():
                                output = f"Error: {path_str} is a directory."
                                self.progress.add_action("READ", path_str, "FAILED: Is Directory")
                            else:
                                output = full_path.read_text(encoding="utf-8")
                                self.progress.add_action("READ", path_str, "SUCCESS")

                    elif fn_name == "find_package":
                        pkg = args.get("package_name")
                        eco = args.get("ecosystem")
                        if not pkg or not eco:
                            output = "Error: Missing package_name or ecosystem"
                        else:
                            cmd = ""
                            if eco == "python":
                                cmd = f"pip index versions {pkg}"
                            elif eco == "node":
                                cmd = f"npm view {pkg} versions"

                            if cmd:
                                res = self.executor.run(cmd, gate="shell", timeout=30)
                                if res.returncode == 0:
                                    output = res.stdout[:2000] + ("..." if len(res.stdout) > 2000 else "")
                                    self.progress.add_action("FIND_PKG", f"{eco}:{pkg}", "SUCCESS")
                                else:
                                    output = f"Error finding package: {res.stderr or res.stdout}"
                                    self.progress.add_action("FIND_PKG", f"{eco}:{pkg}", "FAILED")
                            else:
                                output = f"Error: Unsupported ecosystem '{eco}'"
                    else:
                        output = f"Error: Unknown tool '{fn_name}'"

                # pylint: disable-next=broad-exception-caught
                except Exception as e:
                    output = f"Error executing tool: {e}"
                    self.progress.add_action("TOOL_ERROR", fn_name, f"FAILED: {e}")

                session.add_tool_result(tool_id, output)

            # Get next response from LLM
            response = await session.send()

        return response
