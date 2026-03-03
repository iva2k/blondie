# src/cli/git.py

"""Git CLI wrapper for Blondie agent."""

import subprocess
from pathlib import Path

from agent.executor import Executor
from agent.policy import Policy
from llm.journal import Journal


class GitCLI:
    """Safe git wrapper with policy gating."""

    def __init__(self, repo_path: Path, policy: Policy, journal: Journal | None = None, user: str | None = None, email: str | None = None):
        self.repo_path = repo_path
        self.policy = policy
        self._cwd = repo_path
        self.journal = journal or Journal()
        self.executor = Executor(repo_path, policy, self.journal)

        if user and email:
            self.configure_author(user, email)

    def run(self, *args: str, check: bool = True, capture_output: bool = False, expect_error: bool = False) -> subprocess.CompletedProcess:
        """Run git command with policy check."""
        cmd_list = ["git", *args]
        gate = f"git-{args[0]}"

        # We use a longer timeout (5 min) for git operations
        result = self.executor.run(cmd_list, gate=gate, timeout=300, expect_error=expect_error)

        if result.stderr == "SKIPPED_BY_POLICY":
            raise PermissionError(f"Git action '{args[0]}' forbidden by POLICY.yaml")

        if check and result.returncode != 0:
            raise subprocess.CalledProcessError(result.returncode, cmd_list, output=result.stdout, stderr=result.stderr)

        if not capture_output:
            if result.stdout:
                self.journal.print(result.stdout.strip())
            if result.stderr:
                self.journal.print(result.stderr.strip())

        return subprocess.CompletedProcess(
            args=cmd_list,
            returncode=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
        )

    def configure_author(self, user: str, email: str) -> None:
        """Set git user and email for this repo."""
        # We use subprocess directly to bypass policy checks for configuration
        try:
            subprocess.run(
                ["git", "config", "user.name", user],
                cwd=self.repo_path,
                check=True,
                capture_output=True
            )
            subprocess.run(
                ["git", "config", "user.email", email],
                cwd=self.repo_path,
                check=True,
                capture_output=True
            )
        except subprocess.CalledProcessError as e:
            self.journal.print(f"⚠️ Failed to configure git author: {e}")

    def checkout_branch(self, branch: str) -> None:
        """Safe branch checkout (creates if needed)."""
        if self.branch_exists(branch):
            self.checkout(branch)
        else:
            self.run("checkout", "-b", branch)
            self.journal.print(f"✅ Created [green]{branch}[/]")

    def checkout(self, branch: str) -> None:
        """Checkout existing branch."""
        self.run("checkout", branch)
        self.journal.print(f"✅ Switched to [green]{branch}[/]")

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

    def add(self, path: str | Path, force: bool = False) -> None:
        """Stage specific file."""
        if force:
            self.run("add", "-f", str(path))
        else:
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
        result = self.run("diff", "--quiet", "HEAD", capture_output=True, check=False, expect_error=True)
        return result.returncode == 0

    def create_pr_branch(self, task_id: str) -> str:
        """Full PR-ready branch workflow."""
        branch_name = f"task-{task_id}"

        if self.current_branch() != branch_name:
            self.checkout_branch(branch_name)

        status = self.status()
        if status.strip():
            self.journal.print(f"💾 Changes detected:\n{status}")
            self.add_all()
            self.commit(f"task {task_id}")
            self.push(branch_name)

        return branch_name

    def merge_if_clean(self, branch: str, target_branch: str = "main", exclude_files: list[str] | None = None) -> bool:
        """Merge branch if tests pass."""
        if not self.is_clean():
            self.journal.print("❌ Cannot merge: dirty working directory")
            return False

        permission = self.policy.check_permission("git-merge")
        if permission != "allow":
            self.journal.print(f"⏸️  Merge requires {permission}")
            return False

        try:
            self.run("checkout", target_branch)
            self.run("pull", "origin", target_branch)

            if exclude_files:
                self.run("merge", "--no-ff", "--no-commit", branch)
                for path in exclude_files:
                    # Try to restore from HEAD (target branch version)
                    if self.run("checkout", "HEAD", "--", path, check=False).returncode != 0:
                        # If not in HEAD, unstage (remove from index)
                        self.run("rm", "--cached", "-f", path, check=False)
                        # Remove from working dir to keep clean state
                        full_path = self.repo_path / path
                        if full_path.exists():
                            full_path.unlink()
                self.run("commit", "--no-edit")
            else:
                self.run("merge", "--no-ff", branch)

            self.run("push", "origin", target_branch)
            self.journal.print(f"✅ Merged [bold green]{branch}[/] to {target_branch}")
            return True
        except subprocess.CalledProcessError:
            self.journal.print("❌ Merge failed")
            self.run("merge", "--abort", check=False)
            return False


def main():
    """Simple unit test."""
    policy = Policy()
    git = GitCLI(Path("."), policy)
    print(f"Current branch: {git.current_branch()}")


if __name__ == "__main__":
    main()
