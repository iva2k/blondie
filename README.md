# blondie

## Autonomous AI Coding Agent

Blondie is a fully autonomous coding agent that attaches to an existing git repository, reads a backlog of tasks (`TASKS.md`), and executes them according to defined policies (`POLICY.yaml`). It handles planning, coding, testing, and deployment (via CLI wrappers).

It is designed to run as a Docker container or a standalone binary on a Linux instance.

Blondie implements a recursive orchestrator using **Skills as Tools** for dynamic and adaptive workflows.

## Documentation

- [**Deployment Guide**](docs/DEPLOY.md): How to deploy Blondie to manage your repo.
- [**Development Guide**](docs/DEVELOP.md): How to contribute to Blondie's codebase or debug it locally.
- [**Architecture v2**](docs/ARCHITECTURE2.md): The current recursive skill orchestration architecture.
- [**Skills System**](docs/SKILLS.md): How to write and modify agent skills.

## Project Structure

```text
blondie/
├── .agent/                   # Blondie's own config (git-ignored secrets)
│   ├── dev.yaml              # Development environment configuration
│   ├── ISSUES.md             # Issues
│   ├── llm_config.yaml       # LLM Models configuration
│   ├── POLICY.yaml           # Autonomy rules
│   ├── project.yaml          # Self-description
│   ├── secrets.env.yaml      # LLM keys, tokens (mounted externally)
│   ├── SPEC.md               # Project high-level specification
│   └── TASKS.md              # Project backlog tasks
├── blog/                     # Blog articles
├── docker/
│   ├── Dockerfile            # Python 3.12-slim
│   ├── docker-entrypoint.sh  # Main runner `blondie run`
│   └── systemd-install.sh    # Binary deploy helper
├── docs/                     # Blondie self-docs
│   ├── DEPLOY.md             # Deployment instructions
│   ├── DEVELOP.md            # Development instructions
│   ├── ARCHITECTURE1.md      # v1 Architecture (Procedural)
│   └── ARCHITECTURE2.md      # v2 Architecture (Recursive)
├── scripts/                  # Dev scripts and utils
├── skills/                   # Core SKILL files
├── src/                      # Core runtime
│   ├── agent/                # Main runtime
│   │   ├── context.py        # LLM Context gatherer
│   │   ├── executor.py       # Shell/git/cli wrapper
│   │   ├── llm_config.py     # llm_config.yaml Models/Providers config
│   │   ├── loop.py           # Main task loop
│   │   ├── loop2.py          # v2 Orchestrator loop
│   │   ├── policy.py         # POLICY.yaml parser
│   │   ├── progress.py       # progress.txt keeper
│   │   ├── project.py        # project.yaml parser (also loads dev.yaml)
│   │   ├── router.py         # LLM router - OpenAI/Anthropic/etc.
│   │   ├── tasks.py          # TASKS.md parser
│   │   └── tooled.py         # Tooled LLM calls
│   ├── cli/                  # CLI Wrappers (no MCP servers)
│   │   ├── vercel.py         # vercel --prod wrapper
│   │   ├── netlify.py        # netlify deploy wrapper
│   │   └── git.py            # Git automation
│   ├── lib/                  # Utilities
│   │   └── gitignore.py      # .gitignore file parser
│   ├── llm/                  # Model routing
│   │   ├── client.py         # HTTP abstraction
│   │   ├── journal.py        # Journal keeper
│   │   └── skill.py         # Skill files parser
│   └── repo/                 # Multi-repo management
│       ├── scanner.py        # Discover projects
│       └── adapter.py        # project.yaml parser
├── templates/                # Repo bootstrap templates {{Handlebars}}
│   ├── llm_config.yaml       # Default llm_config
│   ├── POLICY.yaml           # Default POLICY
│   ├── project.yaml          # Default project
│   ├── SPEC.md               # Default SPEC.md
│   └── TASKS.md              # Default TASKS.md
├── tests/                    # Tests
│   ├── agent/                # Unit tests
│   │   ├── test_policy.py    #
│   │   ├── test_project.py   #
│   │   ├── test_tasks.py     #
│   ├── cli/                  # Unit tests
│   │   ├── test_git.py       #
│   ├── llm/                  # Unit tests
│   │   ├── test_llm.py       #
├── pyproject.toml            # Poetry 2.0+
├── pytest.ini                # pythonpath=src
└── README.md
```

## Architecture

Blondie is evolving from a procedural script in [Architecture v1](docs/ARCHITECTURE1.md) to a recursive AI agent in [Architecture v2](docs/ARCHITECTURE2.md).

| Feature           | v1: Procedural Loop     | v2: Recursive Orchestrator (Current)           |
| :---------------- | :---------------------- | :--------------------------------------------- |
| **Control Flow**  | Python Code (`loop.py`) | LLM (`loop2.py` + `coding_orchestrator` skill) |
| **Context**       | Shared/Global           | Stacked/Isolated                               |
| **Tooling**       | Hardcoded (Shell/File)  | Dynamic (Skills + Primitives)                  |
| **Debugging**     | Linear Retry Loop       | Intelligent Sub-Agent Call                     |
| **Extensibility** | Modify Python Code      | Add `.skill.md` file                           |

## Quick Start (Deploy)

The easiest way to get started is with the **Local-First HTML Wizard**. It runs in your browser to securely configure your project, then gives you a simple Docker command to run the agent.

```bash
# 1. Download the Wizard
# Go to the repository and save `init.html` to your computer.

# 2. Run the Wizard
# Open init.html in your browser. It will guide you through setup and
# provide a `blondie_config.zip` file to download.

# 3. Prepare Your Project
# mkdir my-project && cd my-project
# unzip /path/to/your/blondie_config.zip

# 4. Run the Agent
# The wizard will provide the exact Docker command. It will look like this:
docker build -f docker/Dockerfile -t blondie:latest .
docker run -d --restart always \
           -v $(pwd):/workspace \
           -v ~/.blondie/secrets.env.yaml:/workspace/.agent/secrets.env.yaml \
           blondie:latest
```

## Secret Interpolation

Blondie automatically substitutes secrets in project.yaml:

```text
# project.yaml
deploy: vercel --token {{secret:cloud.vercel.token}} --prod

# Renders as:
deploy: vercel --token V3rC3l_t0k3n_ABC123... --prod
```
