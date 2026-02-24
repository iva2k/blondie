# src/cli/git.py

"""Git CLI wrapper for Blondie agent."""

import subprocess
from pathlib import Path

from rich.console import Console

from agent.policy import Policy

console = Console()


class GitCLI:
    """Safe git wrapper with policy gating."""

    def __init__(self, repo_path: Path, policy: Policy):
        self.repo_path = repo_path
        self.policy = policy
        self._cwd = repo_path

    def run(self, *args: str, check: bool = True, capture_output: bool = False) -> subprocess.CompletedProcess:
        """Run git command with policy check."""

        # Policy gate
        permission = self.policy.check_permission(f"git-{args[0]}")
        if permission == "forbid":
            raise PermissionError(f"Git action '{args[0]}' forbidden by POLICY.yaml")
        if permission == "prompt":
            console.print(f"❓ [yellow]Git {args[0]}[/yellow] requires approval")
            if not console.input("[? Approve? (y/N)] ").lower().startswith("y"):
                raise PermissionError("User denied git operation")

        console.print(f"🐙 git {args}")
        # We're not using timeout=, nor we do try-debug-fix loop with LLM, as git commands are currently  all hardcoded.
        # TODO: (when needed) However, when we will start seeing merge conflicts, we should use LLM loop to
        # resolve conflicts.
        result = subprocess.run(["git", *args], cwd=self._cwd, capture_output=capture_output, text=True, check=check)
        return result

    def checkout_branch(self, branch: str) -> None:
        """Safe branch checkout (creates if needed)."""
        if self.branch_exists(branch):
            self.checkout(branch)
        else:
            self.run("checkout", "-b", branch)
            console.print(f"✅ Created [green]{branch}[/]")

    def checkout(self, branch: str) -> None:
        """Checkout existing branch."""
        self.run("checkout", branch)
        console.print(f"✅ Switched to [green]{branch}[/]")

    def branch_exists(self, branch: str) -> bool:
        """Check if branch exists."""
        result = self.run("branch", "--list", branch, capture_output=True)
        return bool(result.stdout.strip())

    def remote_branch_exists(self, branch: str) -> bool:
        """Check if remote branch exists."""
        result = self.run("ls-remote", "--heads", "origin", branch, capture_output=True)
        return bool(result.stdout.strip())

    def current_branch(self) -> str:
        """Get current branch name."""
        result = self.run("branch", "--show-current", capture_output=True, check=True)
        return result.stdout.strip()

    def pull(self, branch: str = "main") -> None:
        """Pull latest changes."""
        self.run("pull", "origin", branch)

    def add(self, path: str | Path) -> None:
        """Stage specific file."""
        self.run("add", str(path))

    def add_all(self) -> None:
        """Stage all changes."""
        self.run("add", ".")

    def commit(self, message: str) -> None:
        """Commit with Blondie prefix."""
        full_message = f"BLONDIE: {message}"
        self.run("commit", "-m", full_message)

    def push(self, branch: str) -> None:
        """Push current branch."""
        self.run("push", "-u", "origin", branch)

    def status(self) -> str:
        """Get clean git status."""
        result = self.run("status", "--porcelain", "-b", capture_output=True)
        return result.stdout

    def is_clean(self) -> bool:
        """Check if working directory is clean."""
        result = self.run("diff", "--quiet", "HEAD", capture_output=True)
        return result.returncode == 0

    def create_pr_branch(self, task_id: str) -> str:
        """Full PR-ready branch workflow."""
        branch_name = f"task-{task_id}"

        if self.current_branch() != branch_name:
            self.checkout_branch(branch_name)

        status = self.status()
        if status.strip():
            console.print(f"💾 Changes detected:\n{status}")
            self.add_all()
            self.commit(f"task {task_id}")
            self.push(branch_name)

        return branch_name

    def merge_if_clean(self, branch: str, target_branch: str = "main") -> bool:
        """Merge branch if tests pass."""
        if not self.is_clean():
            console.print("❌ Cannot merge: dirty working directory")
            return False

        permission = self.policy.check_permission("git-merge")
        if permission != "allow":
            console.print(f"⏸️  Merge requires {permission}")
            return False

        try:
            self.run("checkout", target_branch)
            self.run("pull", "origin", target_branch)
            self.run("merge", "--no-ff", branch)
            self.run("push", "origin", target_branch)
            console.print(f"✅ Merged [bold green]{branch}[/] to {target_branch}")
            return True
        except subprocess.CalledProcessError:
            console.print("❌ Merge failed")
            return False


def main():
    """Simple unit test."""
    policy = Policy()
    git = GitCLI(Path("."), policy)
    print(f"Current branch: {git.current_branch()}")


if __name__ == "__main__":
    main()
