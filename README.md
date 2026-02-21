# blondie

Helpful AI coding agent

- Fully autonomous coder driven by `TASKS.md`, `POLICY.yaml` files
- Easy to deploy - run docker instance or install binary on Linux instance
- Easy to configure - create `secrets.env.yaml` file

## Project Structure

```text
blondie/
├── .agent/                    # Blondie's own config (git-ignored secrets)
│   ├── project.yaml           # Self-description as a project
│   ├── POLICY.yaml             # Blondie's autonomy rules
│   ├── TASKS.md              # Blondie's bootstrap backlog
│   └── secrets.env.yaml      # LLM keys, Vercel tokens (mounted externally)
├── src/                       # Core agent modules
│   ├── agent/                # Main runtime
│   │   ├── loop.py           # Main task loop
│   │   ├── executor.py       # Shell/git/cli wrapper
│   │   └── policy.py         # POLICY.yaml parser
│   ├── llm/                  # Model routing
│   │   ├── router.py         # OpenAI/Anthropic/generic
│   │   └── client.py         # HTTP abstraction
│   ├── repo/                 # Multi-repo management
│   │   ├── scanner.py        # Discover projects
│   │   └── adapter.py        # project.yaml parser
│   ├── cli/                  # Wrappers (no MCP servers)
│   │   ├── vercel.py         # vercel --prod wrapper
│   │   ├── netlify.py        # netlify deploy wrapper
│   │   └── git.py            # Branch/merge automation
│   └── state/                # SQLite models
│       ├── db.py             # Task locks, logs
│       └── models.py         # Task, Lock schemas
├── templates/                 # Repo bootstrap templates
│   ├── project.yaml.template
│   ├── POLICY.yaml.template    # Default gates
│   └── TASKS.md.template
├── tests/                     # E2E user journeys
│   ├── single_repo.test.sh   # Standalone test scripts
│   ├── swarm.test.sh
│   └── autonomy.test.sh
├── docker/
│   ├── Dockerfile
│   ├── docker-entrypoint.sh  # Main runner
│   └── systemd-install.sh    # Binary deploy helper
├── docs/                      # Blondie self-docs
│   ├── README.md            # Deploy instructions
│   └── ARCHITECTURE.md       # Module diagram
└── pyproject.toml            # Python packaging
```

## Development and Debugging

Until this project can bootstrap and self-improve, it is necessary to code MVP and debug it locally.

### Debugging

TODO: TBD

### Unit tests

```bash
# Run unit tests
poetry install && poetry run pytest -v
```

## First Deploy Command

```bash
git clone [<@iva2k/blondie>](https://github.com/iva2k/blondie.git)
cd blondie
rm -f poetry.lock && poetry lock && poetry install --only=main --no-root
docker build -f docker/Dockerfile -t blondie:bootstrap .
docker run -v $(pwd):/workspace -v ./secrets:/secrets blondie:bootstrap
```

## Usage Instructions

```bash
# 1. Copy template
cp .agent/secrets.env.EXAMPLE.yaml .agent/secrets.env.yaml

# 2. Fill required values (minimum for bootstrap):
#    - llm.openai.api_key OR llm.anthropic.api_key OR llm.custom.*
#    - cloud.vercel.token OR cloud.netlify.token (repo-specific)

# 3. Secure mount for Docker
docker run -v $(pwd):/workspace \
           -v $(pwd)/.agent/secrets.env.yaml:/workspace/.agent/secrets.env.yaml \
           blondie:bootstrap

# 4. Binary deploy (systemd)
sudo cp secrets.env.yaml /etc/blondie/secrets.env.yaml
sudo chown root:blondie /etc/blondie/secrets.env.yaml
sudo chmod 600 /etc/blondie/secrets.env.yaml
```

## Secret Interpolation

Blondie automatically substitutes secrets in project.yaml:

```text
# project.yaml
deploy: vercel --token {{secret:cloud.vercel.token}} --prod

# Renders as:
deploy: vercel --token V3rC3l_t0k3n_ABC123... --prod

``
