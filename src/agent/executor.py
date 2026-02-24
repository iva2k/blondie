# src/agent/executor.py

"""Commands executor."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console

from agent.policy import Policy

console = Console()


@dataclass
class CommandResult:
    """Command result dataclass."""

    command: str
    returncode: int
    stdout: str
    stderr: str


class Executor:
    """Shell command executor obeying POLICY.yaml autonomy gates."""

    def __init__(self, repo_path: Path, policy: Policy):
        self.repo_path = repo_path
        self.policy = policy

    def _check_gate(self, action: str) -> bool:
        """Return True if action is allowed to run, False if blocked."""
        permission = self.policy.check_permission(action)
        if permission == "allow":
            return True
        if permission == "forbid":
            console.print(f"⛔ Action '{action}' forbidden by POLICY.yaml")
            return False
        # prompt
        console.print(f"❓ Action '{action}' requires approval (POLICY.yaml)")
        answer = console.input("[Approve? (y/N)] ").strip().lower()
        if not answer.startswith("y"):
            console.print("⏭️  Skipping command.")
            return False
        return True

    def run(self, command: str, *, gate: str | None = None, timeout: int = 120) -> CommandResult:
        """Run a shell command in repo, optionally gated by autonomy policy."""
        if gate and not self._check_gate(gate):
            return CommandResult(command=command, returncode=0, stdout="", stderr="SKIPPED_BY_POLICY")

        console.print(f"💻 [dim]{command}[/dim] (timeout: {timeout}s)")
        try:
            proc = subprocess.Popen(
                command,
                cwd=self.repo_path,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE,
                text=True,
            )
            try:
                stdout, stderr = proc.communicate(input="n\n", timeout=timeout)
            except subprocess.TimeoutExpired as ex:
                proc.kill()
                if sys.platform == "win32":
                    subprocess.run(f"taskkill /F /T /PID {proc.pid}", shell=True, capture_output=True, check=False)
                stdout, stderr = proc.communicate()
                raise subprocess.TimeoutExpired(command, timeout, stdout, stderr) from ex

            if proc.returncode == 0:
                console.print("✅ command ok")
            else:
                console.print(f"❌ command failed (exit {proc.returncode})")

            return CommandResult(
                command=command,
                returncode=proc.returncode,
                stdout=stdout,
                stderr=stderr,
            )
        except subprocess.TimeoutExpired as e:
            console.print(f"⏱️  Command timed out after {timeout}s")
            return CommandResult(
                command=command,
                returncode=124,
                stdout=str(e.stdout or ""),
                stderr=str(e.stderr or f"Timeout after {timeout}s"),
            )

    def run_install(self) -> CommandResult:
        """Run install command."""
        cmd = self.policy.commands.get("install")
        if not cmd:
            console.print("ℹ️  No 'install' command configured, skipping.")
            return CommandResult("install (skipped)", 0, "", "")
        # installs may pull binaries / packages
        return self.run(cmd, gate="install-binary", timeout=600)

    def run_tests(self) -> CommandResult:
        """Run tests command."""
        cmd = self.policy.commands.get("test")
        if not cmd:
            console.print("ℹ️  No 'test' command configured, skipping.")
            return CommandResult("test (skipped)", 0, "", "")

        console.print("🧪 Running tests...")
        return self.run(cmd, timeout=600)

    def run_build(self) -> CommandResult:
        """Run build command."""
        cmd = self.policy.commands.get("build")
        if not cmd:
            console.print("ℹ️  No 'build' command configured, skipping.")
            return CommandResult("build (skipped)", 0, "", "")
        return self.run(cmd, timeout=300)
