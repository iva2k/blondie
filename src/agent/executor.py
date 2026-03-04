# src/agent/executor.py

"""Commands executor."""

from __future__ import annotations

import asyncio
import contextlib
import re
import shlex
import subprocess
import sys
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

from agent.policy import Policy
from llm.journal import Journal


@dataclass
class CommandResult:
    """Command result dataclass."""

    command: str
    returncode: int
    stdout: str
    stderr: str


class CommandTimeoutError(Exception):
    """Raised when a command execution times out."""

    def __init__(self, result: CommandResult):
        self.result = result
        super().__init__(f"Command timed out: {result.command}")


class Executor:
    """Shell command executor obeying POLICY.yaml autonomy gates."""

    def __init__(self, repo_path: Path, policy: Policy, journal: Journal | None = None):
        self.repo_path = repo_path
        self.policy = policy
        self.journal = journal or Journal()

    def _check_gate(self, action: str) -> bool:
        """Return True if action is allowed to run, False if blocked."""
        permission = self.policy.check_permission(action)
        if permission == "allow":
            return True
        if permission == "forbid":
            self.journal.print(f"⛔ Action '{action}' forbidden by POLICY.yaml")
            return False
        # prompt
        self.journal.print(f"❓ Action '{action}' requires approval (POLICY.yaml)")
        # TODO: (now) Implement better architecture than calling journal.console()
        answer = self.journal.console.input("[Approve? (y/N)] ").strip().lower()
        if not answer.startswith("y"):
            self.journal.print("⏭️  Skipping command.")
            return False
        return True

    async def run(
        self,
        command: str | list[str],
        *,
        gate: str | None = None,
        expect_error: bool = False,
        interaction_callback: Callable[[str, str, str], Awaitable[str]] | None = None,
    ) -> CommandResult:
        """Run a shell command in repo, optionally gated by autonomy policy."""
        if sys.platform == "win32":
            command_str = subprocess.list2cmdline(command) if isinstance(command, list) else command
        else:
            command_str = shlex.join(command) if isinstance(command, list) else command

        # Check for blocked file write patterns (echo/printf/cat ... > or | tee)
        if re.search(
            r"(?:^|[;&|]\s*)(?:echo|printf|cat)\b.*?(?:>|\|\s*(?:sudo\s+)?tee\b)",
            command_str,
            re.IGNORECASE | re.DOTALL,
        ) and not self._check_gate("shell-files"):
            return CommandResult(
                command=command_str,
                returncode=125,
                stdout="",
                stderr="BLOCKED (use tool calls and plan actions to generate code)",
            )

        if gate and not self._check_gate(gate):
            return CommandResult(command=command_str, returncode=125, stdout="", stderr="SKIPPED_BY_POLICY")

        self.journal.print(f"💻 [dim]{command}[/dim]")
        start_time = time.perf_counter()

        process = None
        stdout_acc: list[str] = []
        stderr_acc: list[str] = []

        try:
            process = await asyncio.create_subprocess_shell(
                command_str,
                cwd=self.repo_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.PIPE,
            )

            new_output_event = asyncio.Event()

            async def read_stream(stream, buffer):
                while True:
                    line = await stream.readline()
                    if not line:
                        break
                    buffer.append(line.decode(errors="replace"))
                    new_output_event.set()

            # Start reading tasks
            read_stdout = asyncio.create_task(read_stream(process.stdout, stdout_acc))
            read_stderr = asyncio.create_task(read_stream(process.stderr, stderr_acc))

            async def monitor_loop():
                if not interaction_callback:
                    await process.wait()
                    return

                idle_threshold = 2.0  # Seconds to wait before considering "idle" for interaction
                last_interaction_output_len = 0
                process_exit_task = asyncio.create_task(process.wait())

                try:
                    while process.returncode is None:
                        new_output_event.clear()
                        output_wait_task = asyncio.create_task(new_output_event.wait())

                        done, pending = await asyncio.wait(
                            [process_exit_task, output_wait_task],
                            return_when=asyncio.FIRST_COMPLETED,
                            timeout=idle_threshold,
                        )

                        for task in pending:
                            if task is not process_exit_task:
                                task.cancel()

                        if process_exit_task in done:
                            break

                        if output_wait_task in done:
                            continue

                        # Timeout -> Idle
                        current_stdout_len = len(stdout_acc)
                        current_stderr_len = len(stderr_acc)
                        total_len = current_stdout_len + current_stderr_len

                        if total_len > last_interaction_output_len:
                            stdout_str = "".join(stdout_acc)
                            stderr_str = "".join(stderr_acc)

                            try:
                                response = await interaction_callback(command_str, stdout_str, stderr_str)
                                last_interaction_output_len = total_len

                                if response:
                                    if response.strip().upper() == "^C":
                                        self.journal.print("Interaction LLM response: ^C")
                                        process.kill()
                                        break

                                    self.journal.print(f"Interaction LLM response: {response}")
                                    if process.stdin:
                                        input_bytes = (response + "\n").encode()
                                        process.stdin.write(input_bytes)
                                        await process.stdin.drain()
                            except Exception as e:  # pylint: disable=broad-exception-caught
                                self.journal.print(f"Interaction error: {e}")

                    await process_exit_task
                finally:
                    if not process_exit_task.done():
                        process_exit_task.cancel()
                        with contextlib.suppress(asyncio.CancelledError):
                            await process_exit_task

            await monitor_loop()
            await asyncio.gather(read_stdout, read_stderr)

            stdout = "".join(stdout_acc)
            stderr = "".join(stderr_acc)

            duration = time.perf_counter() - start_time
            rc = process.returncode if process.returncode is not None else -1
            self.journal.log_shell(command_str, rc, stdout, stderr, duration, expect_error)
            return CommandResult(
                command=command_str,
                returncode=rc,
                stdout=stdout,
                stderr=stderr,
            )
        except asyncio.CancelledError:  # NOSONAR
            if process:
                try:
                    process.kill()
                except Exception:  # pylint: disable=broad-exception-caught
                    pass
            duration = time.perf_counter() - start_time
            stdout = "".join(stdout_acc)
            stderr = "".join(stderr_acc) + "\nTimeout/Cancelled"
            self.journal.log_shell(command_str, 124, stdout, stderr, duration)
            result = CommandResult(
                command=command_str,
                returncode=124,
                stdout=stdout,
                stderr=stderr,
            )
            raise CommandTimeoutError(result) from None

    async def run_install(self) -> CommandResult:
        """Run install command."""
        cmd = self.policy.commands.get("install")
        if not cmd:
            self.journal.print("ℹ️  No 'install' command configured, skipping.")
            return CommandResult("install (skipped)", 0, "", "")
        # installs may pull binaries / packages
        try:
            return await asyncio.wait_for(self.run(cmd, gate="install-binary"), timeout=600)
        except CommandTimeoutError as e:
            return e.result

    async def run_tests(self) -> CommandResult:
        """Run tests command."""
        cmd = self.policy.commands.get("test")
        if not cmd:
            self.journal.print("ℹ️  No 'test' command configured, skipping.")
            return CommandResult("test (skipped)", 0, "", "")

        self.journal.print("🧪 Running tests...")
        try:
            return await asyncio.wait_for(self.run(cmd), timeout=600)
        except CommandTimeoutError as e:
            return e.result

    async def run_build(self) -> CommandResult:
        """Run build command."""
        cmd = self.policy.commands.get("build")
        if not cmd:
            self.journal.print("ℹ️  No 'build' command configured, skipping.")
            return CommandResult("build (skipped)", 0, "", "")
        try:
            return await asyncio.wait_for(self.run(cmd), timeout=300)
        except CommandTimeoutError as e:
            return e.result
