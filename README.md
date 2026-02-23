# blondie

Helpful AI coding agent

- Fully autonomous coder driven by `TASKS.md`, `POLICY.yaml` files
- Easy to deploy - run docker instance or install binary on Linux instance
- Easy to configure - create `secrets.env.yaml` file

## Project Structure

```text
blondie/
├── .agent/                   # Blondie's own config (git-ignored secrets)
│   ├── POLICY.yaml           # Autonomy rules  
│   ├── project.yaml          # Self-description
│   ├── secrets.env.yaml      # LLM keys, tokens (mounted externally)
│   └── TASKS.md              # Bootstrap backlog
├── src/                      # Core runtime
│   ├── agent/                # Main runtime
│   │   ├── executor.py       # Shell/git/cli wrapper
│   │   ├── loop.py           # Main task loop
│   │   ├── policy.py         # POLICY.yaml parser
│   │   ├── project.py        # project.yaml parser
│   │   └── tasks.py          # TASKS.md parser
│   ├── llm/                  # Model routing
│   │   ├── router.py         # OpenAI/Anthropic/generic
│   │   └── client.py         # HTTP abstraction
│   ├── repo/                 # Multi-repo management
│   │   ├── scanner.py        # Discover projects
│   │   └── adapter.py        # project.yaml parser
│   └── cli/                  # CLI Wrappers (no MCP servers)
│       ├── vercel.py         # vercel --prod wrapper
│       ├── netlify.py        # netlify deploy wrapper
│       └── git.py            # Git automation
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
├── docs/                     # Blondie self-docs
│   ├── DEPLOY.md             # Deployment instructions
│   ├── DEVELOP.md            # Development instructions
│   └── ARCHITECTURE.md       # Module diagram
├── docker/
│   ├── Dockerfile            # Python 3.12-slim
│   ├── docker-entrypoint.sh  # Main runner `blondie run`
│   └── systemd-install.sh    # Binary deploy helper
├── pyproject.toml            # Poetry 2.0+
├── pytest.ini                # pythonpath=src
└── README.md
```

## Development and Debugging

Until this project can bootstrap and self-improve, it is necessary to code MVP and debug it locally.

### Debugging

TODO: TBD

### Unit tests

```bash
# Run unit tests
poetry install && poetry run pytest -v
# or
poetry install && poe check
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
