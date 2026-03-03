# src/llm/journal.py

"""Journaling module for Blondie."""

import datetime
import json
from pathlib import Path
from typing import Any

from rich.console import Console


class Journal:
    """Logger for agent activities and LLM interactions."""

    def __init__(self, root_dir: Path | str | None = None, project_id: str | None = None):
        self.root_dir = Path(root_dir) if root_dir else None
        self.project_id = project_id
        self.console = Console()
        self.current_log_file: Path | None = None

    def start_task(self, task_id: str) -> None:
        """Start a new logging session for a task."""
        if not self.root_dir:
            return

        # Sanitize task ID for folder name (e.g. BLONDIE-020 -> task020)
        safe_id = "".join(c for c in task_id if c.isalnum() or c in ("-", "_"))

        if self.project_id:
            safe_project_id = "".join(c for c in self.project_id if c.isalnum() or c in ("-", "_"))
            task_dir = self.root_dir / safe_project_id / f"task{safe_id}"
        else:
            task_dir = self.root_dir / f"task{safe_id}"
        task_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.datetime.now().strftime("%Y-%m%d-%H%M")
        self.current_log_file = task_dir / f"{timestamp}.log"

        self.write_raw(f"=== Journal started for task {task_id} at {timestamp} ===\n")

    def print(self, *args: Any, truncate: int | None = None, **kwargs: Any) -> None:
        """Print to console and log to file."""
        if truncate is not None:
            console_args = []
            for arg in args:
                s = str(arg)
                if len(s) > truncate:
                    console_args.append(s[:truncate] + "... [truncated]")
                else:
                    console_args.append(arg)
            self.console.print(*console_args, **kwargs)
        else:
            self.console.print(*args, **kwargs)

        if self.current_log_file:
            # Simple text logging for console output
            text = " ".join(str(arg) for arg in args)
            self.write_raw(f"[CONSOLE] {text}\n")

    def log_chat(
        self,
        operation: str,
        provider: str,
        prompt: str,
        response: Any,
        system_prompt: str | None = None,
        model: str | None = None,
        endpoint: str | None = None,
        title: str | None = None,
    ) -> None:
        """Log LLM interaction details."""
        if self.current_log_file:
            # Extract content/usage from response if available
            content = str(response)
            if hasattr(response, "content"):
                content = response.content

            cost = getattr(response, "cost_usd", None)

            tokens = None
            if hasattr(response, "tokens_used"):
                tokens = {"total_tokens": response.tokens_used}
            entry = {
                "type": "LLM",
                "title": title,
                "operation": operation,
                "provider": provider,
                "model": model,
                "endpoint": endpoint,
                "tokens": tokens,
                "cost": cost,
                "tool_calls": len(response.tool_calls) if hasattr(response, "tool_calls") and response.tool_calls else 0,                
                "content": content,
                "prompt": prompt,
                "system_prompt": system_prompt,  # prompt[:1000] + "..." if len(prompt) > 1000 else prompt,
                "timestamp": datetime.datetime.now().isoformat(),
            }

            self.write_raw(f"\n=== LLM CHAT ({operation}) ===\n")
            self.write_raw(json.dumps(entry, indent=2, default=str))
            self.write_raw("\n==============================\n")
        self.print(f"📋 [{provider.upper()}] {operation}: {response.tokens_used}t")

    def log_shell(self, command: str, returncode: int, stdout: str, stderr: str, expect_error: bool = False) -> None:
        """Log shell command execution."""

        if self.current_log_file:
            entry = {
                "type": "SHELL",
                "command": command,
                "returncode": returncode,
                "stdout": stdout,
                "stderr": stderr,
                "timestamp": datetime.datetime.now().isoformat(),
            }

            self.write_raw(f"\n=== SHELL ({command[:50]}...) ===\n")
            self.write_raw(json.dumps(entry, indent=2, default=str))
            self.write_raw("\n==============================\n")

        if returncode == 0:
            self.print("✅ command ok")
        elif returncode == 124:  # Timeout
            self.print(f"⏱️ command {stderr}")
        elif expect_error:
            self.print(f"❌ command failed normally (was expected) (exit {returncode}) Error: {stderr or stdout}")
        else:
            self.print(f"❌ command failed (exit {returncode}) Error: {stderr or stdout}")

    def write_raw(self, text: str) -> None:
        """Write raw text to log file."""
        if self.current_log_file:
            try:
                with open(self.current_log_file, "a", encoding="utf-8") as f:
                    f.write(text)
            # pylint: disable-next=broad-exception-caught
            except Exception as e:
                self.console.print(f"[red]Journal write failed: {e}[/red]")
