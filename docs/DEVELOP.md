# Development Guide

Before AI bot can develop itself, we do it the old-fashion way.

This guide covers how to set up your environment to develop, debug, and test the Blondie agent itself.

## 1. Prerequisites

* **Python 3.10+**
* **Poetry**: Dependency management (`pip install poetry`), will install task runner `poe`.
* **Git**: Version control.
* **Docker**: (Optional) For building the container image.

## 2. Setup

Clone the repository and install dependencies:

```bash
git clone https://github.com/iva2k/blondie.git
cd blondie
poetry install
```

## 3. Development Workflow

Formatting, linting and unit tests (with coverage, goal is >=80%) should be run after code edits:

Blondie requires a "target repository" to operate on. We simulate this locally using a `_tmp` directory structure.

### A. Prepare Test Environment

We use a script to create a temporary git repository in `_tmp/repo` linked to a bare remote in `_tmp/remote.git`. This allows the agent to pull, push, and create branches safely without messing up your actual projects.

```bash
# Wipes _tmp/ and creates a fresh repo with sample config
poe setup-dev
```

The `_tmp/repo` will contain:

* `.agent/`: Configuration files copied from `templates/project-calculator/.agent` and `secrets.env.yaml` copied from the project workspace `.agent/` folder if file exists.
* `README.md`, `.gitignore`, etc.

If your project workspace `.agent/secrets.env.yaml` does not include API keys, you must provide secrets for the agent to use:

```bash
cp .agent/secrets.env.EXAMPLE.yaml _tmp/repo/.agent/secrets.env.yaml
nano _tmp/repo/.agent/secrets.env.yaml
# Add your LLM API keys
```

### B. Run the Agent

To run the agent against this temporary repository TBD:

```bash
# Run the v2 Orchestrator
poe run
```

This command equates to:
`python -m agent.cli run _tmp/repo --journal-dir _tmp/repo/_logs --v2`

### C. Debugging with VS Code

The project includes a `.vscode/launch.json` with pre-configured debug profiles:

* **Blondie: Run Orchestrator (_tmp/repo)**: Runs the agent in debug mode against the `_tmp/repo`.
* **Python: Debug Tests**: Run pytest with debugger.

**Recommended Loop:**

1. Make code changes in `src/` or `skills/`.
2. Reset environment: `poe setup-dev`.
3. Set breakpoints in VS Code.
4. Run "Blondie: Run Orchestrator" via F5.

### D. Iterative Development

After running and exiting the agent, the `_tmp/repo/` folder can contain partially completed task. The agent can be restarted (e.g. after fixing a bug) - it has logic to pick up where it left off by checking local branches to find a task is in progress, and pick it up instead of starting a new one.

In production it is still useful to be able to restart the agent and continue working on an already started task, so it is not just a for-development feature.

## 4. Code Quality & Testing

We enforce strict quality standards. Formatting, linting and unit tests (with coverage, goal is >=80%) should be run after code edits:

```bash
# Run formatting, linting, type checking, and unit tests
poe check
```

100% PASS should be achieved before committing any code.

To run specific tests:

```bash
poetry run pytest tests/agent/test_loop2.py
```

## 5. Tools & Scripts

### Snapshotting Sessions

If you want to save the state of a run (logs, repo state) for analysis (e.g. if you encounter an interesting agent session):

```bash
poe snapshot-dev
```

This copies `_tmp` to a timestamped folder (e.g., `_tmp.2024-0310-1200`).

### Model & Cost Scraping

To update the known LLM models and pricing:

```bash
poe fetch-models
```

This updates `.agent/llm.yaml` by scraping provider pages or querying APIs.

This `.agent/llm.yaml` file is also copied into `_tmp/repo/.agent/` for debug runs by `poe setup-dev` task (`setup-dev` script).

## 6. Architecture Overview for Developers

* **Entry Point**: `src/agent/cli.py` handles argument parsing.
* **Orchestrator**: `src/agent/loop2.py` initializes the system.
* **Skills**: located in `skills/`. If you modify a `.skill.md` file, the changes are picked up on the next run (parsed by `src/llm/skill.py`).
* **Tools**: `src/agent/tooled.py` contains the Python implementation of tools like `run_shell` or `git_commit`.

### Adding a New Skill

1. Create `skills/my_new_skill.skill.md`.
2. Define frontmatter (`input-schema`, `tools`, etc.).
3. Add it to `skills/coding_orchestrator.skill.md` (or relevant parent skill) in the `tools` list.

### Adding a New Tool (Python)

1. Define the implementation method in `src/agent/tooled.py` (ToolHandler class).
2. Register it in `self.tool_implementations` and `TOOL_DEFINITIONS` (if hardcoded) or allow dynamic registration.
