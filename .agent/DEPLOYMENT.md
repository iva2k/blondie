# Blondie Deployment Guide

This guide details how to deploy Blondie on a new machine to autonomously manage a web application. We will use a **React/TypeScript** project as the example target.

## Prerequisites

1. **Linux Machine** (VPS, EC2, or local machine) with Docker installed.
2. **Git** installed.
3. **API Keys**:
   * LLM Provider (e.g., OpenAI API Key or Anthropic API Key).
   * Cloud Provider (e.g., Vercel Access Token for deployment).

---

## 1. Prepare the Target Repository

Blondie attaches to your existing git repository.

[ ]  TODO: Implement tool for easy creation of git repo

You must add an `.agent` directory containing configuration files so Blondie understands how to build, test, and deploy your specific app.

[ ]  TODO: Implement tool for easy creation of .agent folder and all files in it (use templates, need templates per project type, e.g. python vs. TypeScript, React vs. Svelte, Vercel vs. Netlify, etc. - need multi-dimensional templates / or modular ones)

Navigate to your React/TypeScript project root and create the config folder:

```bash
cd my-react-app
mkdir .agent
```

### A. Define Project Metadata (`.agent/project.yaml`)

Map your project's scripts to Blondie's standard commands.

```yaml
id: my-react-app
languages: [typescript, javascript]
task_source: TASKS.md
commands:
  install: npm install
  test: npm test -- --watchAll=false
  build: npm run build
  # Uses CLI wrapper for Vercel, injecting the token from secrets
  deploy: vercel --prod --token {{secret:vercel_token}}
policy: POLICY.yaml
docs: [README.md, src/docs/]
```

### B. Set Autonomy Rules (`.agent/POLICY.yaml`)

Define the "Safe Mode" rules.

```yaml
# Blondie Self-Policy

## Autonomy Gates
git-merge: allow          # Allow merging PRs automatically if tests pass
deploy-preview: allow     # Allow deploying to preview URLs
deploy-prod: prompt       # Require human approval for production
install-package: allow    # Allow agent to install new npm packages

## Retry Logic
max_test_retries: 3       # Try to fix code 3 times before giving up
```

### C. Create Backlog (`.agent/TASKS.md`)

Initialize the task list. Blondie reads this file to decide what to do next.

```markdown
# Tasks

Status: id | priority | title | depends_on

## Todo
- [ ] 001 | P0 | Update landing page hero text |
- [ ] 002 | P1 | Fix navigation bar z-index bug |
```

---

## 2. Configure Secrets

On the machine where Blondie will run (NOT in the git repo), create a `secrets.env.yaml` file. This file contains sensitive keys and should never be committed to version control.

[ ]  TODO: Implement tool for easy creation of secrets.env.yaml file

**File Location Example:** `/etc/blondie/secrets.env.yaml`

```yaml
llm:
  openai:
    api_key: "sk-proj-..."
  anthropic:
    api_key: "claude-..."

cloud:
  vercel:
    token: "V3rC3l_t0k3n_..."
```

---

## 3. Run Blondie (Docker)

Run the Blondie agent as a Docker container. You must mount:

1. The target repository (to `/workspace`).
2. The secrets file (to `/workspace/.agent/secrets.env.yaml`).

```bash
docker run -d \
  --name blondie-agent \
  --restart always \
  -v /path/to/my-react-app:/workspace \
  -v /etc/blondie/secrets.env.yaml:/workspace/.agent/secrets.env.yaml \
  blondie:v1
```

[ ]  TODO: Implement tool for easy setup of docker run command, add it to system startup.

---

## 4. Verification & Workflow

### Check Logs

Monitor the agent to ensure it has picked up the configuration:

```bash
docker logs -f blondie-agent
```

**Expected Output:**

```text
[INFO] Blondie v1 started
[INFO] Project detected: my-react-app
[INFO] Policy loaded: deploy-prod=prompt
[INFO] Claimed task 001: Update landing page hero text
[INFO] Executing: npm install...
```

### Human Intervention

If Blondie reaches a step requiring approval per settings in POLICY.yaml file (e.g., `deploy-prod`), it will pause and wait for input (via CLI attachment or configured chat integration).

To approve via CLI if running interactively:

```text
❓ DEPLOY-PROD requires approval
Command: vercel --prod --token ...
[Approve / Skip / Edit command]
> Approve
```
