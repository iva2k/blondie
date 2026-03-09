# src/llm/journal.py

"""Journaling module for Blondie."""

import datetime
import json
from contextlib import contextmanager
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
        self.indent_level = 0

    def indent(self) -> None:
        """Increase indentation level."""
        self.indent_level += 1

    def dedent(self) -> None:
        """Decrease indentation level."""
        if self.indent_level > 0:
            self.indent_level -= 1

    @contextmanager
    def span(self, title: str):
        """Context manager for a logging span."""
        self.print(f"╭── {title}")
        self.indent()
        try:
            yield
        finally:
            self.dedent()
            self.print(f"╰── {title}")

    def start_task(self, task_id: str) -> None:
        """Start a new logging session for a task."""
        if not self.root_dir:
            return

        # Sanitize task ID for folder name (e.g. "020" -> "task-020")
        safe_id = "".join(c for c in task_id if c.isalnum() or c in ("-", "_", "="))

        if self.project_id:
            safe_project_id = "".join(c for c in self.project_id if c.isalnum() or c in ("-", "_", "="))
            task_dir = self.root_dir / safe_project_id / f"task{safe_id}"
        else:
            task_dir = self.root_dir / f"task{safe_id}"
        task_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.datetime.now().strftime("%Y-%m%d-%H%M")
        self.current_log_file = task_dir / f"{timestamp}.log"

        self.write_raw(f"=== Journal started for task {task_id} at {timestamp} ===\n")

    def print(self, *args: Any, truncate: int | None = None, **kwargs: Any) -> None:
        """Print to console and log to file."""
        indent_str = "│   " * self.indent_level
        console_args = []

        for arg in args:
            if truncate is not None:
                s = str(arg)
                if len(s) > truncate:
                    console_args.append(s[:truncate] + "... [truncated]")
                else:
                    console_args.append(arg)
            else:
                console_args.append(arg)

        if indent_str:
            self.console.print(indent_str, end="")
        self.console.print(*console_args, **kwargs)

        if self.current_log_file:
            # Simple text logging for console output
            text = " ".join(str(arg) for arg in args)
            self.write_raw(f"{indent_str}{text}\n")

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
                "indent": self.indent_level,
                "title": title,
                "operation": operation,
                "provider": provider,
                "model": model,
                "endpoint": endpoint,
                "tokens": tokens,
                "cost": cost,
                "tool_calls": len(response.tool_calls)
                if hasattr(response, "tool_calls") and response.tool_calls
                else 0,
                "content": content,
                "prompt": prompt,
                "system_prompt": system_prompt,  # prompt[:1000] + "..." if len(prompt) > 1000 else prompt,
                "timestamp": datetime.datetime.now().isoformat(),
            }

            indent_str = "│   " * self.indent_level
            self.write_raw(f"{indent_str}\n{indent_str}=== LLM CHAT ({operation}) ===\n")
            json_str = json.dumps(entry, indent=2, default=str)
            if indent_str:
                json_str = "\n".join(indent_str + line for line in json_str.splitlines())
            self.write_raw(json_str)
            self.write_raw(f"\n{indent_str}==============================\n")
        self.print(f"📋 [{provider.upper()}] {operation}: {response.tokens_used}t")

    def log_shell(
        self,
        command: str,
        returncode: int,
        stdout: str,
        stderr: str,
        duration: float = 0.0,
        expect_error: bool = False,
    ) -> None:
        """Log shell command execution."""

        if self.current_log_file:
            entry = {
                "type": "SHELL",
                "indent": self.indent_level,
                "command": command,
                "duration": duration,
                "returncode": returncode,
                "stdout": stdout,
                "stderr": stderr,
                "timestamp": datetime.datetime.now().isoformat(),
            }

            indent_str = "│   " * self.indent_level
            self.write_raw(f"{indent_str}\n{indent_str}=== SHELL ({command[:50]}...) ===\n")
            json_str = json.dumps(entry, indent=2, default=str)
            if indent_str:
                json_str = "\n".join(indent_str + line for line in json_str.splitlines())
            self.write_raw(json_str)
            self.write_raw(f"\n{indent_str}==============================\n")

        if returncode == 0:
            self.print(f"✅ command ok ({duration:.2f}s)")
        elif returncode == 124:  # Timeout
            self.print(f"⏱️ command {stderr} ({duration:.2f}s)")
        elif expect_error:
            self.print(
                f"❌ command failed normally (was expected) (exit {returncode})"
                f" Error: {stderr or stdout} ({duration:.2f}s)"
            )
        else:
            self.print(f"❌ command failed (exit {returncode}) Error: {stderr or stdout} ({duration:.2f}s)")

    def write_raw(self, text: str) -> None:
        """Write raw text to log file."""
        if self.current_log_file:
            try:
                with open(self.current_log_file, "a", encoding="utf-8") as f:
                    f.write(text)
            # pylint: disable-next=broad-exception-caught
            except Exception as e:
                self.console.print(f"[red]Journal write failed: {e}[/red]")

    def get_archive_path(self, filename: str) -> Path | None:
        """Get path for an archive file in the current log directory."""
        if not self.current_log_file:
            return None

        if filename.startswith("."):
            return self.current_log_file.with_suffix(filename)

        return self.current_log_file.parent / filename
