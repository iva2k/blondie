# Calculator Spec

"Calculator" is a simple Calculator project for Blondie testing.

## Directory Structure

```text
testproject/
├── .agent/                   # Self-config
│   ├── POLICY.yaml           # Autonomy rules  
│   ├── project.yaml          # Self-description
│   ├── secrets.env.yaml      # LLM keys, tokens
│   ├── SPEC.md               # Specifications doc
│   └── TASKS.md              # Bootstrap backlog
├── src/                      # Core runtime
├── tests/                    # Tests
├── pyproject.toml            # Poetry 2.0+
├── pytest.ini                # pythonpath=src
└── README.md
```
