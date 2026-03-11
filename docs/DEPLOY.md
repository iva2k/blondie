# Blondie Deployment Guide

Blondie operates as a virtual software engineer living in a container. To employ it, you need to provide:

1. **Host Machine**: Any machine with Docker installed.
2. **The Workspace**: A git repository (new or existing) mounted to the container.
3. **The Keys**: Credentials for LLMs and Cloud providers (`secrets.env.yaml`).
4. **The Instructions**:
   - `SPEC.md`: The high-level product specification (What to build).
   - `TASKS.md`: The backlog of work items (What to do next).
   - `ISSUES.md`: A scratchpad for the agent to log observations or problems (optional).
   - `POLICY.yaml`: The rules of engagement (Autonomy levels).
   - `dev.yaml`: Language and development tools configuration (Linters, formatters).
   - `llm_config.yaml`: Model selection and parameters (e.g. GPT-4o, Claude 3.5).
   - `project.yaml`: Project definition (Commands, metadata).

The [#onboarding flow](#quick-start-wizard) automates the creation of these files, or you can create them [#manually](#manual-configuration-advanced).

---

## Quick Start Wizard

The wizard handles secrets generation, project templating, and deployment configuration in one go.

### 1. Run the Wizard

First, build the Docker image (if you haven't already):

```bash
docker build -f docker/Dockerfile -t blondie:latest .
```

Then execute the interactive `init` command. We mount `~/.blondie` to store your global secrets securely on the host, and the current directory as the workspace.

```bash
mkdir -p ~/.blondie
cd /path/to/my/project  # Directory to initialize

docker run --rm -it \
  -v ~/.blondie:/root/.blondie \
  -v $(pwd):/workspace \
  blondie:latest init
```

### 2. The Interview

The wizard will guide you through the following steps:

#### A. Secrets Setup

If `~/.blondie/secrets.env.yaml` is missing, it will ask:

- "Enter your OpenAI/Anthropic API Key:"
- "Enter your Cloud Provider Token (Vercel/Netlify/AWS) [Optional]:"

#### B. Project Initialization

It detects if the current directory is empty or has code.

- **Empty Directory**: "Choose a starter template: [1] Python Basic [2] React/Vite [3] Node Express..."
- **Existing Code**: "Analyzing repository... Detected Python. Generating `.agent/` config..."
- **Product Spec**: "What are you building?" (Writes to `SPEC.md`).
- **Initial Task**: "What are the first tasks?" [Default: Setup project] (Writes to `TASKS.md`).

#### C. Deployment Configuration

It asks where the final product should be deployed:

- "Select Deployment Target: [1] Docker (Self-hosted) [2] Vercel [3] Netlify [4] Custom SSH"
- Depending on choice, it configures `project.yaml` commands (e.g., `deploy: vercel --prod`).

---

## 3. Run the Agent

Once initialized, run Blondie in background (daemon) mode.

```bash
docker run -d \
  --name blondie \
  --restart always \
  -v $(pwd):/workspace \
  -v ~/.blondie/secrets.env.yaml:/workspace/.agent/secrets.env.yaml \
  blondie:latest
```

Blondie is now running. It will read `SPEC.md` and `TASKS.md` to begin working on the first available task.

---

## Operating the Agent

### Monitoring & Logs

Watch the agent plan, code, and test in real-time.

```bash
docker logs -f blondie
```

### Assigning Work

Edit `.agent/TASKS.md` via your favorite editor and commit/push to git.

```markdown
- [ ] 005 | P1 | Add dark mode toggle to header |
```

### Logs & Artifacts

The agent persists its state and logs within your workspace:

- `.agent/logs/`: Detailed execution logs and LLM conversations (Journal).
- `.agent/progress.txt`: A summary of recent actions.

---

## Manual Configuration (Advanced)

If you prefer to configure manually, create an `.agent/` directory in the root of your repository with these files below. To get started you can copy one of template projects in`templates/` folder.

### 1. `SPEC.md`

Defines your high-level product requirements and "North Star" goals.

```markdown
# Product Spec
Goal: Create a calculator app that supports RPN mode.
Users: Engineers and students.
```

### 2. `project.yaml`

Defines your project type. Maps generic actions to your specific project commands.

```yaml
id: my-project
languages: [python]
git_user: "Blondie Bot"
git_email: "blondie@example.com"
task_source: TASKS.md
commands:
  install: poetry install
  test: poetry run pytest
  # Secrets are injected at runtime from secrets.env.yaml
  deploy: ./deploy.sh --token {{secret:cloud.vercel.token}}
policy: POLICY.yaml
dev_config: dev.yaml
```

### 3. `POLICY.yaml`

Defines the agent autonomy level and safety gates.

```yaml
# Autonomy Gates (allow | prompt | forbid)
git-merge: allow          # Auto-merge PRs if tests pass
deploy-prod: prompt       # Wait for human approval before running deploy command
shell-exec: allow         # Allow running shell commands

limits:
  max_daily_cost_usd: 5.0  # Hard stop if cost exceeds this
  max_test_retries: 3
```

### 4. `TASKS.md`

The backlog of work.

```markdown
# Tasks
## Todo
Status: id | priority | title | depends_on
- [ ] 001 | P0 | Setup project structure |
```

### 5. `dev.yaml`

Development environment configuration. See some available pre-configured files in `templates/dev.*.yaml` to start from.

```yaml
package_manager: poetry
linter: ruff
formatter: black
```

### 6. `secrets.env.yaml`

You can use `.agent/secrets.env.EXAMPLE.yaml` as a template for your `secrets.env.yaml` file.

Store this in `~/.blondie/` or `.agent/` (git-ignored).

```yaml
llm:
  openai:
    api_key: "sk-..."
  anthropic:
    api_key: "sk-ant-..."
  groq:
    api_key: "gsk-..."

cloud:
  vercel:
    token: "..."
```

### 7. `llm_config.yaml`

Model definitions and model selection per different operation.

```yaml
providers:
  anthropic:
    model: claude-3-5-sonnet-20240620
    temperature: 0.1
  groq:
    api_type: openai
    base_url: https://api.groq.com/openai/v1
    default_model: llama-3.3-70b-versatile
  # To use OpenAI:
  # openai:
  #   model: gpt-4o
  #   temperature: 0.1
  
  # You can add more providers here. Do not add multiple models here, instead edit `operations` section.

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

> **⚠️ Important:** Ensure `.agent/secrets.env.yaml` is added to your `.gitignore` file to prevent accidental commit of credentials.

### 8. Maintenance

#### Updating the Agent

To upgrade to the latest version:

```bash
git pull
docker build -f docker/Dockerfile -t blondie:latest .

# Stop and remove the old container
docker stop blondie
docker rm blondie

# Start a new one with the updated image
docker run -d --name blondie ... (see Start command above)
```

### 9. Troubleshooting

#### Permission Denied (Linux)

If you see permission errors writing to `.agent/`, ensure the container has the right UID/GID or run with `user: $(id -u):$(id -g)` in the docker command.

#### API Key Errors

Check `docker logs blondie`. If you see 401/403 errors, verify your keys in `~/.blondie/secrets.env.yaml` and restart the container.

#### Agent Loop / Stuck

If the agent seems stuck on a task:

1. Check logs: `docker logs --tail 100 blondie`
2. Restart: `docker restart blondie`
3. If it persists, the agent may be in a logic loop. Edit `.agent/TASKS.md` to guide it differently: make the task description more specific, break it into smaller sub-tasks, or add a note about the failed approach.

#### Windows Users

If running on Windows Command Prompt, replace `$(pwd)` with `%cd%`.
If running on PowerShell, use `${PWD}`.
