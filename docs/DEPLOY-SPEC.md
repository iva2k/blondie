# Deployment Wizard Implementation Spec

**Status**: Draft
**Source**: [DEPLOY.md](DEPLOY.md)

## Goal

Implement a seamless "Quick Start" onboarding wizard (`blondie init`) that automates the setup of secrets, configuration, and project structure, implementing the user journey defined in the Deployment Guide.

## 1. CLI Architecture Refactor

**Current State**: `src/agent/cli.py` is a single `click.command` entry point.
**Target State**: `src/agent/cli.py` becomes a `click.group` entry point.

### Commands

1. **`run`**: The agent loop.
   - `python -m agent.cli run [repo_path]`
2. **`init`**: The wizard.
   - `python -m agent.cli init`

## 2. Wizard Logic (`src/agent/cli.py init`)

### A. Secrets Setup

**Path**: `~/.blondie/secrets.env.yaml` (Host) mapped to `/root/.blondie/secrets.env.yaml` (Container).

1. Check if secrets file exists.
2. If missing, Interactive Prompts:
   - `llm.openai.api_key`
   - `llm.anthropic.api_key`
   - `llm.groq.api_key`
   - `cloud.vercel.token`
3. Action: Generate and write YAML file.
   - *Note*: If `secrets.env.yaml` exists, load it and only prompt for missing keys or confirm existing ones.
4. **Validation & Model Discovery**:
   - Run `scripts/fetch_models.py` (or equivalent logic) using the secrets.
   - Serves as a connectivity test for API keys.
   - Generates `.agent/llm.yaml` (list of available models/costs) in the workspace.
   - If validation fails, warn user and offer to re-enter keys.

### B. Workspace Setup

**Path**: `$(pwd)` (Host) mapped to `/workspace` (Container).

- Detect if `/workspace` is empty or contains an existing project.
  - If empty (or not a git repo), run `git init`.
    - *Note*: Warn user to configure `git remote add origin ...` manually later.
  - **Stack Detection** (Existing Project):
    - Analyze files to detect language (e.g., `pyproject.toml` -> Python, `package.json` -> Node).
    - Pre-fill `project.yaml` (`languages`, `commands`) and select appropriate `dev.yaml` defaults.
    - **Interactive Verification**: Prompt user to confirm or edit detected commands (e.g., "Detected install command: `poetry install`. Accept? [Y/n/edit]").

### C. Templating

**Source**:

- `templates/basic/` (Generic/Empty)
- `templates/python/` (Python specific)
- `templates/node/` (Node/JS specific)

**Target**: `/workspace/`.

1. **Overwrite Protection**: If `.agent/` exists, ask before overwriting config files.
2. **Copying**:
   - **Empty Directory**: Prompt for template (Default: Basic). Copy full structure.
   - **Existing Project**: Create `.agent/` folder. Copy config files (`project.yaml`, `POLICY.yaml`, `llm_config.yaml`, `dev.yaml`).
   - **.gitignore**:
     - If missing: Copy default.
     - If exists: Append `.agent/secrets.env.yaml` and `.agent/llm.yaml` if not present.
   - **Permissions**:
     - If running as root (Docker default), attempt to `chown` generated files to match `/workspace` owner to avoid permission lockout on Host.

### D. Customization Interview

1. **Spec**: Prompt "What are you building?" -> Writes/Updates `SPEC.md`.
2. **Project Identity**: Prompt "Project ID/Name?" [Default: folder name] -> Updates `project.yaml` (`id`, `name`).
3. **Tasks**: Prompt "First tasks?" -> Writes/Updates `TASKS.md`.
4. **Git Identity**: Prompt "Bot Git Name/Email?" [Default: Blondie Bot] -> Updates `project.yaml`. Bot Identity is useful in a swarm.
5. **Model Provider**: Prompt "Primary AI Provider? [OpenAI/Anthropic]" -> Updates `llm_config.yaml` (sets active provider/model).
6. **Deployment**: Prompt "Target? [Docker/Vercel/Netlify]" -> Updates `project.yaml` deploy command.

### E. Completion and Next Steps

- Print success message.
- Output the exact `docker run` command to copy-paste, ensuring paths match the user's configuration.

## 3. Template Structure

Refactor `templates/` to support directory-based copying.

```text
templates/
└── basic/
    ├── .gitignore
    ├── .agent/
    │   ├── project.yaml
    │   ├── POLICY.yaml
    │   ├── TASKS.md
    │   ├── SPEC.md
    │   ├── ISSUES.md
    │   ├── dev.yaml
    │   └── llm_config.yaml
```

## 4. Implementation Checklist

- [ ] Create `templates/basic/` structure.
- [ ] Refactor `src/agent/cli.py` to `click.group`.
- [ ] Implement `init` command in `src/agent/cli.py init`.
