# Blondie Deployment Guide

Blondie operates as a virtual software engineer living in a container. To employ it, you need to provide:

1. **Host Machine**: Any machine with Docker installed.
2. **The Workspace**: A git repository (new or existing) mounted to the container.
3. **The Keys**: Credentials for git, LLMs, and Cloud providers (`secrets.env.yaml`).
4. **The Instructions**: Content of the [`.agent` directory](#the-agent-directory).

This guide explains how to deploy and configure the Blondie agent to manage your code repositories.

## The `.agent` Directory

Blondie's configuration lives in an `.agent/` directory at the root of your project. This directory contains all the necessary files for the agent to understand its goals, policies, and environment.

- `SPEC.md`: The high-level product specification (What to build).
- `TASKS.md`: The backlog of work items (What to do next).
- `ISSUES.md`: A scratchpad for the agent to log observations or problems (optional).
- `POLICY.yaml`: The rules of engagement (Autonomy levels/Safety gates).
- `dev.yaml`: Language and development tools configuration (Linters, formatters, coding standard).
- `llm_config.yaml`: Model selection and parameters (e.g. GPT-4o, Claude 3.5).
- `project.yaml`: Project definition (Commands, metadata).

---

First, collect all [**Prerequisites**](#1-prerequisites) and perform the [**Installation**](#2-installation-build-image).

Then, choose an onboarding method:

- The recommended [**HTML Wizard**](#3-onboarding-the-html-wizard-recommended)
- or the [**CLI Wizard**](#4-onboarding-the-cli-wizard-advanced).
- For advanced users, [**Manual Configuration**](#7-manual-configuration-advanced) is also an option.

---

## 1. Prerequisites

Before starting, gather the following credentials.

### LLM API Keys

You need at least one LLM provider, but using a few allows you to leverage their individual strengths.

- **OpenAI**: `sk-...`
- **Anthropic**: `sk-ant-...`
- **Groq** (Optional): `gsk-...`

### Git Authentication

Blondie needs credentials to push code and create Pull Requests.

#### Option A: HTTPS Token (Recommended)

For HTTPS repositories (e.g., `https://github.com/user/repo.git`), create a Personal Access Token (PAT).

- **GitHub**: Settings -> Developer Settings -> Personal Access Tokens (Classic). Scopes: `repo`.
- **GitLab**: User Settings -> Access Tokens. Scopes: `api`, `write_repository`.

#### Option B: SSH Keys

If you prefer SSH (e.g., `git@github.com:user/repo.git`), you will skip the token setup in the wizard. Instead, you will have to copy your SSH key to the instance's `~/.ssh` directory and mount it when running the container.

---

## 2. Installation (Build Image)

You need to build the Blondie Docker image on your host machine.

1. Clone the repository:  

   ```bash
   git clone https://github.com/iva2k/blondie.git
   cd blondie
   ```

2. Build the image:  

   ```bash
   docker build -f docker/Dockerfile -t blondie:latest .
   ```

---

## 3. Onboarding: The HTML Wizard (Recommended)

The recommended workflow is to use the **Local-First HTML Wizard**. It runs entirely in your browser, requires no installation dependencies, and lets you securely configure your project.

### Step 1: Download and Run

1. Locate the `blondie.html` file in the root of the `blondie` repository you just cloned.
2. Double-click `blondie.html` to open it in your web browser.
3. In the Wizard you can open a previously created `blondie_config.zip` file to edit your settings.

### Step 2: The Interview

The wizard page will guide you through the following steps. It runs entirely in your browser.

_**NO DATA IS EVER TRANSMITTED OVER THE NETWORK.**_

Copy-paste your tokens and keys to avoid typos.

1. **Secrets Setup**:
   - Enter your API Keys (OpenAI, Anthropic, etc.).
   - Enter your GitHub Token (if using HTTPS).
2. **Template Selection**:
   - Choose a starter template (e.g., Basic, Python, Node.js) to pre-fill configuration.
3. **Project Details**:
   - **Project ID**: A unique name for your agent/project.
   - **Goal**: A high-level description of what you are building (populates `SPEC.md`).
   - **Initial Tasks**: Define the first few tasks for the agent's backlog (`TASKS.md`).
4. **Configuration**:
   - **Deployment Target**: Choose where your app will live (Docker, Vercel, Netlify). This configures the `deploy` command in `project.yaml`.

### Step 3: Download Configuration

After completing the interview, click **"Generate & Download"**. Your browser will download a `blondie_config.zip` file containing a ready-to-use `.agent` directory.

### Step 4: Prepare Your Project

1. Create a new folder for your project and navigate into it.

   ```bash
   mkdir my-new-project
   cd my-new-project
   ```

2. Unzip the `blondie_config.zip` file here. Your folder should now contain the `.agent` directory.
3. If this is a new project, initialize a git repository and connect it to your remote (e.g., on GitHub).

   ```bash
   # Initialize the local repository
   git init

   # Add the remote repository URL
   git remote add origin https://github.com/your-username/my-new-project.git

   # Create an initial commit and push to set the upstream branch
   git add .
   git commit -m "Initial commit with Blondie config"
   git push -u origin main
   ```

---

## 4. Onboarding: The CLI Wizard (Advanced)

If you prefer the command line, you can run the wizard either inside a Docker container or directly in your local Python environment.

### Option A: Using Docker

Execute the interactive `init` command. This mounts `~/.blondie` for global secrets and the current directory as the workspace.

   ```bash
   mkdir -p ~/.blondie
   cd /path/to/my/project  # Directory to initialize

   docker run --rm -it \
     -v ~/.blondie:/root/.blondie \
     -v $(pwd):/workspace \
     blondie:latest init
   ```

### Option B: Using a Local Python Environment

1. Set up your local development environment as described in the **Development Guide** (clone repo, `poetry install`).
2. Navigate to your target project folder and run the wizard via `poetry`.  

   ```bash
   # In your Blondie clone directory
   cd /path/to/blondie

   # Run the init command, targeting your project's directory
   poetry run blondie init /path/to/my/project
   ```

### The Terminal Interview

The CLI wizard will guide you through similar steps as the HTML version:

1. **Secrets**: Asks for storage location (Global `~/.blondie` or Project `.agent/`) and keys.
2. **Stack Detection**: Analyzes existing files (e.g. `pyproject.toml`) to suggest commands.
3. **Templating**: If the directory is empty, prompts to select a configuration template.
4. **Interview**: Prompts for Spec, Project ID, Initial Tasks, and Deployment target.

---

## 5. Running the Agent

Once your project is initialized, run Blondie in the background (daemon mode).

### Standard Run (HTTPS Git)

Use this if you provided a GitHub token in the secrets file.

```bash
docker run -d \
  --name blondie \
  --restart always \
  -v $(pwd):/workspace \
  -v $(pwd)/.agent/secrets.env.yaml:/workspace/.agent/secrets.env.yaml \
  blondie:latest run
```

### SSH Run

If you skipped the token setup and use SSH for git, mount your SSH keys with additional  `-v ~/.ssh:/root/.ssh:ro` argument.

```bash
docker run -d \
  --name blondie \
  --restart always \
  -v ~/.ssh:/root/.ssh:ro \
  -v $(pwd):/workspace \
  -v $(pwd)/.agent/secrets.env.yaml:/workspace/.agent/secrets.env.yaml \
  blondie:latest run
```

Blondie is now running. It will read `SPEC.md` and `TASKS.md` to begin working on the first available task.

## 6. Operating the Agent

### Monitoring & Logs

Watch the agent plan, code, and test in real-time.

```bash
docker logs -f blondie
```

Monitor commits progress: `git log` in your repository.

### Assigning Work

Edit `.agent/TASKS.md` in your favorite editor and commit/push to the `main` branch to assign new work.

```markdown
- [ ] 005 | P1 | Add dark mode toggle to header |
```

### Logs & Artifacts

The agent persists its state and logs within its workspace:

- `.agent/logs/`: Detailed execution logs and LLM conversations (Journal).
- `.agent/progress.txt`: A summary of recent actions.

## 7. Manual Configuration (Advanced)

If you prefer to configure manually, create an `.agent/` directory in the root of your repository with these files below. To get started, you can copy files from one of template projects in `templates/` folder, e.g. `templates/basic/.agent`.

### `SPEC.md`

Defines your high-level product requirements and "North Star" goals.

```markdown
# Product Spec
Goal: Create a calculator app that supports RPN mode.
Users: Engineers and students.
```

### `project.yaml`

Defines your project type and maps generic actions to your specific project commands.

```yaml
id: my-app
name: "My Awesome App"
languages: [python]
git_user: "Blondie Bot"
git_email: "blondie@example.com"
main_branch: main
task_source: TASKS.md
commands:
  install: poetry install
  test: poetry run pytest
  # Secrets are injected at runtime from secrets.env.yaml
  deploy: ./deploy.sh --token {{secret:cloud.vercel.token}}
policy: POLICY.yaml
dev_config: dev.yaml
docs: [README.md]
```

### `POLICY.yaml`

Defines the agent autonomy level and safety gates.

```yaml
# Autonomy Gates (allow | prompt | forbid)
autonomy:
  gates:
    git-merge: allow          # Auto-merge PRs if tests pass
    deploy-docker: prompt     # Wait for human approval before running deploy command
    shell-exec: allow         # Allow running shell commands

limits:
  max_daily_cost_usd: 5.0  # Hard stop if cost exceeds this
  max_test_retries: 3
```

### `TASKS.md`

The agent's backlog of work.

```markdown
# Tasks

Status: id | priority | title | depends_on

## Todo

- [ ] 001 | P0 | Setup project structure |
- [ ] 002 | P1 | Implement user authentication |
```

### `dev.yaml`

Defines the development environment. See some available pre-configured files in `templates/` to start from.

```yaml
environment:
  language: python
  manager: poetry
guidelines:
  - "Use an `src` layout."
  - "Follow PEP 8 via ruff."
```

### `secrets.env.yaml`

**Never commit this file.** Contains API keys and tokens.

You can use `.agent/secrets.env.EXAMPLE.yaml` as a template.

Store this in `~/.blondie/` or `.agent/` (which should be ignored by git).

```yaml
llm:
  openai:
    api_key: "sk-..."
  anthropic:
    api_key: "sk-ant-..."
  groq:
    api_key: "gsk-..."
git:
  github_token: "ghp_..."
cloud:
  vercel:
    token: "..."
```

> ⚠️ Important: Ensure `.agent/secrets.env.yaml` is added to your `.gitignore` file to prevent accidental commit of credentials.

### `llm_config.yaml`

Defines model selection for different operations. See `templates/basic/llm_config.yaml` for a full example.

```yaml
providers:
  anthropic:
    model: claude-3-5-sonnet-20240620
    temperature: 0.1
  groq:
    api_type: openai
    base_url: https://api.openai.com/v1
    default_model: gpt-4o-mini

operations:
  # You can add more provider/models under each operation. Make sure provider matches entry in `providers` section.
  planning:
    - provider: anthropic
      model: claude-3-5-sonnet-20240620
    - provider: groq
      model: openai/gpt-oss-120b
    # Example of multiple models from same provider:
    - provider: groq
      model: llama-3.3-70b-versatile
    # To use OpenAI:
    # - provider: openai
    #   model: gpt-4o
  coding:
    # etc. ...
```

## 8. Maintenance

### Updating the Agent

To upgrade to the latest version:

```bash
git pull
docker build -f docker/Dockerfile -t blondie:latest .

# Stop and remove the old container
docker stop blondie
docker rm blondie

# Start the new container
docker run -d --name blondie
```

## 8. Troubleshooting

### Permission Denied (Linux)

If you see permission errors writing to `.agent/`, ensure the container has the right UID/GID or run with `user: $(id -u):$(id -g)` in the `docker run` command.

### API Key Errors

Check `docker logs blondie`. If you see 401/403 errors, verify your keys in your `secrets.env.yaml` and restart the container.

### Agent Loop / Stuck

If the agent seems stuck on a task:

1. Check logs: `docker logs --tail 100 blondie`
2. Restart: `docker restart blondie`
3. If it persists, the agent may be in a logic loop. Edit `.agent/TASKS.md` to guide it differently: make the task description more specific, break it into smaller sub-tasks, or add a note about the failed approach.

### Windows Users

If running on Windows Command Prompt, replace `$(pwd)` with `%cd%`.

If running on PowerShell, use `${PWD}`.
