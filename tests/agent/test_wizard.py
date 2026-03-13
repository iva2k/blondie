"""Tests for the initialization wizard."""

from pathlib import Path
from unittest.mock import patch

import click
import pytest
import yaml
from click.testing import CliRunner

from agent.wizard import (
    define_project,
    interview,
    setup_secrets,
    setup_workspace,
    stack_detection,
    validate_secrets,
)


@pytest.fixture
def mock_home(tmp_path):
    """Mock Path.home() to return a temp directory."""
    with patch("pathlib.Path.home", return_value=tmp_path):
        yield tmp_path


def test_setup_secrets_new_file(mock_home):
    """Test creating a new secrets file with interactive input."""
    # Simulate user inputs:
    # 1. Storage? 1 (Global)
    # 2. Git Auth? 1 (HTTPS)
    # 3. Update Token? Yes -> gh-token (Wait, has_token is False, so it asks for token directly)
    # 4. OpenAI? Yes -> sk-test
    # 5. Anthropic? No
    # 6. Groq? No
    # 7. Vercel? No
    # (Git token is asked first now)
    inputs = "1\n1\ngh-token\ny\nsk-test\nn\nn\nn\n"

    runner = CliRunner()
    # We invoke a dummy command to run the function in a click context,
    # or just use runner.invoke if we wrap it in a command.
    # But setup_secrets uses click.prompt/confirm directly.
    # The easiest way to test click interaction functions is wrapping them.

    @click.command()
    def cmd():
        setup_secrets()

    result = runner.invoke(cmd, input=inputs)

    assert result.exit_code == 0
    assert "Secrets Setup" in result.output
    assert "✅ Secrets saved" in result.output

    secrets_file = mock_home / ".blondie" / "secrets.env.yaml"
    assert secrets_file.exists()

    with open(secrets_file, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    assert data["llm"]["openai"]["api_key"] == "sk-test"
    assert "anthropic" not in data["llm"]
    assert "vercel" not in data["cloud"]
    assert data["git"]["github_token"] == "gh-token"


def test_setup_secrets_existing_file(mock_home):
    """Test updating an existing secrets file."""
    secrets_dir = mock_home / ".blondie"
    secrets_dir.mkdir()
    secrets_file = secrets_dir / "secrets.env.yaml"

    existing_data = {"llm": {"openai": {"api_key": "sk-existing"}}, "cloud": {}}
    with open(secrets_file, "w", encoding="utf-8") as f:
        yaml.safe_dump(existing_data, f)

    # Inputs:
    # Storage? 1 (Global)
    # Git Auth? 1 (HTTPS) (Token exists? No, so prompt) -> gh-token
    # OpenAI check (skipped because exists)
    # Anthropic? Yes -> sk-ant
    # Groq? No
    # Vercel? No
    inputs = "1\n1\ngh-token\ny\nsk-ant\nn\nn\n"

    @click.command()
    def cmd():
        setup_secrets()

    runner = CliRunner()
    result = runner.invoke(cmd, input=inputs)

    assert result.exit_code == 0
    assert "Found existing secrets" in result.output

    with open(secrets_file, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    assert data["llm"]["openai"]["api_key"] == "sk-existing"
    assert data["llm"]["anthropic"]["api_key"] == "sk-ant"
    assert data["git"]["github_token"] == "gh-token"


def test_setup_secrets_with_config():
    """Test secrets setup picking up providers from llm_config.yaml."""
    runner = CliRunner()

    # Create a workspace with .agent/llm_config.yaml
    # We need to run in isolated filesystem so _get_workspace() picks it up
    with runner.isolated_filesystem() as td:
        ws = Path(td)
        agent_dir = ws / ".agent"
        agent_dir.mkdir()

        # Define custom providers
        (agent_dir / "llm_config.yaml").write_text(
            """
providers:
  custom_prov:
    default_model: model-x
""",
            encoding="utf-8",
        )

        # Inputs:
        # 1. Storage? 2 (Project - inside isolated fs)
        # 2. Git Auth? 1 (HTTPS) -> gh-token
        # 3. Setup custom_prov? Yes -> key
        # 4. Vercel? No
        inputs = "2\n1\ngh-token\ny\nsk-custom\nn\n"

        @click.command()
        def cmd():
            setup_secrets()

        result = runner.invoke(cmd, input=inputs)

        assert "Do you want to set up Custom_prov API Key?" in result.output
        assert "✅ Secrets saved" in result.output

        secrets_file = agent_dir / "secrets.env.yaml"
        assert secrets_file.exists()
        data = yaml.safe_load(secrets_file.read_text(encoding="utf-8"))
        assert data["llm"]["custom_prov"]["api_key"] == "sk-custom"


def test_define_project():
    """Test define_project prompt."""
    runner = CliRunner()

    @click.command()
    def cmd():
        res = define_project()
        click.echo(f"ID: {res['id']}, Repo: {res['git_repo']}")

    # Input: ID=my-app, Repo=http://git
    result = runner.invoke(cmd, input="my-app\nhttp://git\n")
    assert result.exit_code == 0
    assert "ID: my-app, Repo: http://git" in result.output


@patch("agent.wizard.fetch_and_save_models")
def test_validate_secrets_success(mock_fetch):
    """Test validation success path."""
    mock_fetch.return_value = True

    # Mock workspace path in wizard using a patch context on Path
    # However, validate_secrets uses Path("/workspace") or Path.cwd() fallback.
    # We rely on the fallback or mock Path.

    # Since we can't easily mock Path constructor for specific args globally,
    # we'll assume it falls back to cwd if /workspace doesn't exist.

    secrets = {"llm": {"openai": {"api_key": "sk-test"}}}

    @click.command()
    def cmd():
        validate_secrets(secrets)

    runner = CliRunner()
    result = runner.invoke(cmd)

    assert result.exit_code == 0
    assert "Validating Keys" in result.output
    assert "✅ Model list saved" in result.output
    mock_fetch.assert_called_once()


def test_setup_secrets_errors(mock_home):
    """Test error handling in setup_secrets."""
    # 1. Test mkdir OSError
    runner = CliRunner()
    with runner.isolated_filesystem():
        with patch("pathlib.Path.mkdir", side_effect=OSError("Permission denied")):

            @click.command()
            def cmd():
                setup_secrets()

            result = runner.invoke(cmd, input="2\nn\nn\nn\nn\n")
            assert "Warning: Could not create" in result.output

    # 2. Test yaml load error
    secrets_dir = mock_home / ".blondie"
    if not secrets_dir.exists():
        secrets_dir.mkdir()
    (secrets_dir / "secrets.env.yaml").write_text(":", encoding="utf-8")  # Invalid YAML

    @click.command()
    def cmd_load():
        setup_secrets()

    result = runner.invoke(cmd_load, input="1\n1\ngh-token\nn\nn\nn\n")
    assert "Error loading secrets" in result.output


@patch("agent.wizard.fetch_and_save_models")
def test_validate_secrets_failure(mock_fetch):
    """Test validation failure path."""
    mock_fetch.return_value = False

    runner = CliRunner()

    @click.command()
    def cmd():
        validate_secrets({})

    result = runner.invoke(cmd)
    assert "Could not verify any API keys" in result.output


@patch("agent.wizard.subprocess.run")
def test_setup_workspace_fresh(mock_run, tmp_path):
    """Test workspace setup in an empty directory."""
    # Ensure we use the real template directory relative to the source
    # tmp_path will act as our workspace

    runner = CliRunner()

    @click.command()
    def cmd():
        # Confirm git init: Yes
        # Template: 1 (Basic)
        # (Templates copy proceeds automatically without overwrite prompt since dest doesn't exist)
        setup_workspace(target_dir=tmp_path)

    result = runner.invoke(cmd, input="y\n1\n")

    assert result.exit_code == 0
    assert "Initialized empty git repository" in result.output
    assert "Created .agent/project.yaml" in result.output

    # Check Git init was called
    mock_run.assert_called()
    args = mock_run.call_args[0][0]
    assert args[:2] == ["git", "init"]
    assert str(tmp_path) in args[2]

    # Check files
    agent_dir = tmp_path / ".agent"
    assert agent_dir.exists()
    assert (agent_dir / "project.yaml").exists()
    assert (agent_dir / "POLICY.yaml").exists()
    assert (tmp_path / ".gitignore").exists()


@patch("agent.wizard.subprocess.run")
def test_setup_workspace_with_def(mock_run, tmp_path):
    """Test workspace setup applying project definition."""
    # Ensure stdout is a string so 'in' checks don't raise TypeError on MagicMock
    mock_run.return_value.stdout = ""

    runner = CliRunner()

    project_def = {"id": "new-id", "git_repo": "https://git.com/repo.git"}

    @click.command()
    def cmd():
        setup_workspace(target_dir=tmp_path, project_def=project_def)

    # Confirm git init: Yes, Template: 1
    result = runner.invoke(cmd, input="y\n1\n")
    assert result.exit_code == 0
    assert "Applied project definition" in result.output

    agent_dir = tmp_path / ".agent"
    project_data = yaml.safe_load((agent_dir / "project.yaml").read_text(encoding="utf-8"))
    assert project_data["id"] == "new-id"
    assert project_data["git_repo"] == "https://git.com/repo.git"


@patch("agent.wizard.subprocess.run")
def test_setup_workspace_existing(mock_run, tmp_path):
    """Test workspace setup in an existing directory with collisions."""
    # 1. Setup existing state
    (tmp_path / ".git").mkdir()
    (tmp_path / ".gitignore").write_text("*.log", encoding="utf-8")

    agent_dir = tmp_path / ".agent"
    agent_dir.mkdir()
    (agent_dir / "project.yaml").write_text("id: old", encoding="utf-8")

    runner = CliRunner()

    @click.command()
    def cmd():
        # Confirm git init? (Skipped logic, but input stream might need alignment if logic changed)
        # Logic says: if .git exists, it prints "Git repository detected" and doesn't prompt.
        # Template: 1

        # Overwrite project.yaml? No
        setup_workspace(target_dir=tmp_path)

    # 1 for template, 'n' for overwrite confirmation
    result = runner.invoke(cmd, input="1\nn\n")

    assert result.exit_code == 0
    assert "Git repository detected" in result.output
    mock_run.assert_not_called()

    # Check project.yaml was NOT overwritten
    assert (agent_dir / "project.yaml").read_text(encoding="utf-8") == "id: old"

    # Check .gitignore was updated
    gitignore_content = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    assert "*.log" in gitignore_content
    assert ".agent/secrets.env.yaml" in gitignore_content


@patch("os.getuid", return_value=0, create=True)
@patch("os.chown", create=True)
@patch("os.walk")
def test_setup_workspace_permissions(mock_walk, mock_chown, _mock_getuid, tmp_path):
    """Test permission fixing when running as root."""
    # Mock os.walk to return dummy files
    mock_walk.return_value = [
        (str(tmp_path / ".agent"), ["subdir"], ["file1"]),
    ]

    # Create dummy files so os.walk logic works if it were real,
    # but here we rely on the mock return for the loop.
    # However, the code calls `workspace.stat()`. We need a real path or mocked stat.
    # tmp_path is real.

    runner = CliRunner()

    @click.command()
    def cmd():
        setup_workspace(target_dir=tmp_path)

    result = runner.invoke(cmd, input="y\n1\n")

    assert result.exit_code == 0
    assert "Fixed file permissions" in result.output
    assert mock_chown.called


def test_interview_flow(tmp_path):
    """Test the interactive interview updates files correctly."""
    # 1. Setup workspace with templates
    agent_dir = tmp_path / ".agent"
    agent_dir.mkdir()

    (agent_dir / "SPEC.md").write_text("# Spec\nGoal: <Describe your product goal here>\n", encoding="utf-8")
    (agent_dir / "project.yaml").write_text("id: old\ncommands: {}\n", encoding="utf-8")

    # Mock llm_config with providers to test dynamic lookup
    (agent_dir / "llm_config.yaml").write_text(
        """
providers:
  anthropic:
    default_model: claude-3-5-sonnet-20240620
operations: {}
""",
        encoding="utf-8",
    )
    (agent_dir / "TASKS.md").write_text("# Tasks\n## Todo\n", encoding="utf-8")

    # Inputs:
    # 1. Spec: "My App"
    # 2. Git Name: "Agent Smith"
    # 3. Add Tasks? "y" -> "Task 1" -> ""
    # 4. Provider: "anthropic"
    # 5. Deployment: "vercel"
    # 6. SSH: "n"
    inputs = "My App\nAgent Smith\ny\nTask 1\n\nanthropic\nvercel\nn\n"

    runner = CliRunner()

    @click.command()
    def cmd():
        interview(target_dir=tmp_path)

    result = runner.invoke(cmd, input=inputs)

    assert result.exit_code == 0
    assert "Ready for liftoff" in result.output

    # Verify SPEC.md
    spec_content = (agent_dir / "SPEC.md").read_text(encoding="utf-8")
    assert "Goal: My App" in spec_content

    # Verify project.yaml
    project_data = yaml.safe_load((agent_dir / "project.yaml").read_text(encoding="utf-8"))
    assert project_data["id"] == "old"
    assert project_data["git_user"] == "Agent Smith"
    assert "vercel --prod" in project_data["commands"]["deploy"]

    # Verify TASKS.md
    tasks_content = (agent_dir / "TASKS.md").read_text(encoding="utf-8")
    assert "Task 1" in tasks_content

    # Verify llm_config.yaml
    llm_data = yaml.safe_load((agent_dir / "llm_config.yaml").read_text(encoding="utf-8"))
    assert llm_data["operations"]["planning"][0]["provider"] == "anthropic"
    assert llm_data["operations"]["coding"][0]["model"] == "claude-3-5-sonnet-20240620"

    # Verify output command
    assert "docker run" in result.output
    assert "-v ~/.ssh" not in result.output


def test_stack_detection_poetry(tmp_path):
    """Test stack detection for a Poetry project."""
    agent_dir = tmp_path / ".agent"
    agent_dir.mkdir()
    (agent_dir / "project.yaml").write_text("commands: {}\n", encoding="utf-8")
    (agent_dir / "dev.yaml").write_text("environment: {}\n", encoding="utf-8")

    # Create pyproject.toml with poetry
    (tmp_path / "pyproject.toml").write_text("[tool.poetry]\nname = 'test'", encoding="utf-8")

    runner = CliRunner()

    @click.command()
    def cmd():
        stack_detection(target_dir=tmp_path)

    result = runner.invoke(cmd, input="y\n")

    assert result.exit_code == 0
    assert "Detected: Python (Poetry)" in result.output
    assert "Updated project.yaml" in result.output

    project = yaml.safe_load((agent_dir / "project.yaml").read_text(encoding="utf-8"))
    assert "poetry install" in project["commands"]["install"]
    assert project["languages"] == ["python"]

    dev = yaml.safe_load((agent_dir / "dev.yaml").read_text(encoding="utf-8"))
    assert dev["environment"]["manager"] == "poetry"


def test_stack_detection_node_npm(tmp_path):
    """Test stack detection for a Node/NPM project."""
    agent_dir = tmp_path / ".agent"
    agent_dir.mkdir()
    (agent_dir / "project.yaml").write_text("commands: {}\n", encoding="utf-8")
    (agent_dir / "dev.yaml").write_text("environment: {}\n", encoding="utf-8")

    # Create package.json
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")

    runner = CliRunner()

    @click.command()
    def cmd():
        stack_detection(target_dir=tmp_path)

    result = runner.invoke(cmd, input="y\n")

    assert result.exit_code == 0
    assert "Detected: Node.js (npm)" in result.output

    project = yaml.safe_load((agent_dir / "project.yaml").read_text(encoding="utf-8"))
    assert "npm install" in project["commands"]["install"]
    assert project["languages"] == ["javascript"]


def test_stack_detection_none(tmp_path):
    """Test stack detection when no known files exist."""
    agent_dir = tmp_path / ".agent"
    agent_dir.mkdir()

    runner = CliRunner()

    @click.command()
    def cmd():
        stack_detection(target_dir=tmp_path)

    result = runner.invoke(cmd)

    assert result.exit_code == 0
    assert "No specific stack detected" in result.output
