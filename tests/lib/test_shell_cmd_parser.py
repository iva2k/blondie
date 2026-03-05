"""Unit tests for Shell Command Parser module."""

from lib.shell_cmd_parser import ShellCommandParser


def test_split_commands_basic():
    """Test basic command splitting."""
    assert ShellCommandParser.split_commands("echo hello") == ["echo hello"]
    assert ShellCommandParser.split_commands("cd /tmp && ls") == ["cd /tmp", "ls"]
    assert ShellCommandParser.split_commands("make build; make test") == ["make build", "make test"]
    assert ShellCommandParser.split_commands("cat file | grep x") == ["cat file", "grep x"]
    assert ShellCommandParser.split_commands("cmd1 || cmd2") == ["cmd1", "cmd2"]


def test_split_commands_whitespace():
    """Test splitting with varying whitespace."""
    assert ShellCommandParser.split_commands("cmd1&&cmd2") == ["cmd1", "cmd2"]
    assert ShellCommandParser.split_commands(" cmd1  ;  cmd2 ") == ["cmd1", "cmd2"]
    assert ShellCommandParser.split_commands("cmd1;cmd2 ") == ["cmd1", "cmd2"]
    assert ShellCommandParser.split_commands("  cmd1  ") == ["cmd1"]


def test_gate_detection_shell_files():
    """Test detection of file modification patterns."""
    # Basic redirection
    assert ShellCommandParser.detect_gate("echo hello > world.txt") == "shell-files"
    assert ShellCommandParser.detect_gate("cat file >> append.txt") == "shell-files"
    assert (
        ShellCommandParser.detect_gate(
            'echo \'[[tool.poetry.source]]\nname = "pypi"\nurl = "https://pypi.org/simple"\' >> pyproject.toml'
        )
        == "shell-files"
    )

    # Tee
    assert ShellCommandParser.detect_gate("cat file | tee -a append.txt") == "shell-files"
    assert ShellCommandParser.detect_gate("tee log.txt") == "shell-files"
    assert ShellCommandParser.detect_gate("sudo tee /etc/config") == "shell-files"
    assert ShellCommandParser.detect_gate('set a="echo hello"; sudo $a | tee /etc/config') == "shell-files"

    # Printf
    assert ShellCommandParser.detect_gate("printf 'content' > file.c") == "shell-files"
    assert ShellCommandParser.detect_gate("printf 'content' >> append.cpp") == "shell-files"
    assert ShellCommandParser.detect_gate('printf "$a" | tee -a append.cpp') == "shell-files"


def test_gate_detection_packages():
    """Test detection of package management commands."""
    assert ShellCommandParser.detect_gate("npm install axios") == "add-package"
    assert ShellCommandParser.detect_gate("npm add axios") == "add-package"
    assert ShellCommandParser.detect_gate("pnpm add -D debug") == "add-package"
    assert ShellCommandParser.detect_gate("pip install requests") == "add-package"
    assert ShellCommandParser.detect_gate("poetry add flask") == "add-package"
    assert ShellCommandParser.detect_gate("sudo apt-get install curl") == "add-package"
    assert ShellCommandParser.detect_gate("yum install vim") == "add-package"

    # Non-install commands
    assert ShellCommandParser.detect_gate("npm test") is None
    assert ShellCommandParser.detect_gate("npm run dev") is None
    assert ShellCommandParser.detect_gate("pnpm test") is None
    assert ShellCommandParser.detect_gate("pnpm run dev") is None
    assert ShellCommandParser.detect_gate("pip list") is None


def test_gate_detection_git():
    """Test detection of git commands."""
    assert ShellCommandParser.detect_gate("git merge feature") == "git-merge"
    assert ShellCommandParser.detect_gate("git push origin main") == "git-push"
    assert ShellCommandParser.detect_gate("git pull") is None
    assert ShellCommandParser.detect_gate("git branch --list") is None
    assert ShellCommandParser.detect_gate("git status") is None
    assert ShellCommandParser.detect_gate("git checkout -b new-branch") is None


def test_sudo_handling():
    """Test that sudo is correctly stripped to find the real command."""
    assert ShellCommandParser.detect_gate("sudo npm install") == "add-package"
    assert ShellCommandParser.detect_gate("sudo git merge") == "git-merge"
