# Skills System Documentation

Blondie's capabilities are defined by **Skills**, which are markdown files located in the `skills/` directory. A skill defines an LLM persona, its available tools, context requirements, and operational parameters. It is based on Claude SKILL.md file format, with additional features built on top of frontmatter data record.

## Anatomy of a Skill

A skill file (`.skill.md`) consists of two parts:

1. **YAML Frontmatter**: Configuration metadata (top of file, between `---`).
2. **System Prompt**: The instruction body (Markdown) that becomes the system message for the LLM. Can include placeholders like `{context}`.

### Example

```markdown
---
name: plan_task
description: Generate implementation plan
operation: "planning"
temperature: 0.1
context:
  task: True
  files: True
tools:
  - run_shell
---
# TASK PLANNER

You are an expert planner...

{context}
...
```

## Frontmatter Reference

| Field             | Type        | Description                                                                                                         | Default         |
| :---------------- | :---------- | :------------------------------------------------------------------------------------------------------------------ | :-------------- |
| `name`            | `str`       | Unique identifier for the skill. Used for logging and tool registration.                                            | Filename (stem) |
| `description`     | `str`       | Description of what the skill does. Used when registering the skill as a tool for the Orchestrator.                 | `""`            |
| `operation`       | `str`       | Logical operation name. Used by `LLMRouter` to select the specific model/provider defined in `llm_config.yaml`.     | `"coding"`      |
| `temperature`     | `float`     | Sampling temperature (0.0 to 1.0).                                                                                  | `0.1`           |
| `max-tokens`      | `int`       | Max output tokens.                                                                                                  | `2000`          |
| `context`         | `dict`      | Context sections to include (see Context Generator).                                                                | `None`          |
| `tools`           | `list[str]` | List of tool names (primitives or other skills) available to this skill.                                            | `None`          |
| `user-content`    | `str`       | Template for the initial user message. Can include placeholders like `{task_title}`.                                | `None`          |
| `input-schema`    | `dict`      | JSON Schema for arguments if this skill is called as a tool. If present, this skill is registered as a tool.        | `None`          |
| `output-schema`   | `dict`      | JSON Schema for structured output enforcement (injected into prompt).                                               | `None`          |
| `response-schema` | `str`       | [DEPRECATED]: Name of a registered internal Pydantic model (e.g., `FileEdits`) for parsing and validation.          | `None`          |
| `response-format` | `str`       | [DEPRECATED]: Expected format: `json` or `yaml`. Used if response-schema is not set.                                | `None`          |
| `user-invocable`  | `bool`      | Whether this skill can be directly invoked by the user via CLI (future feature).                                    | `False`         |
| `log-title`       | `str`       | Template for the log entry title in the journal.                                                                    | `""`            |

## Context Generator

The `context` section in frontmatter determines what information is gathered from the repository and injected into the system prompt, replacing `{context}` placeholder.

The `ContextGatherer` collects the requested sections and formats them into a single string containing Markdown headers (e.g., `## CONTEXT`, `### [FILES]`).

System prompt can contain references to the Context items. Current recommended format for references is capitalized label with square brackets enclosed in backticks, e.g. "See \`[FILES]\` section for existing files.". Backticks are recommended for a strong signal to LLM, and square brackets should match how context sub-section headers are formatted.

**Usage in Prompt:**

Include the `{context}` placeholder in your system prompt body to inject the gathered context. It is recommended to insert context before any instructions that reference it, so LLM can make the connection.

### Available Context Sections

| Key         | Labels          | Description                                              | Source            |
|:------------|:----------------|:---------------------------------------------------------|:------------------|
| `cwd`       | CWD, TEMP_DIR   | Current directory, temporary directory.                  | os.getcwd()       |
| `os`        | OS, ARCH, SHELL | Operating system, architecture, and shell info.          | `platform` module |
| `task`      | TASK            | Current active task details (task_id, title, priority).  | `TASKS.md`        |
| `files`     | FILES           | Recursive file listing (respecting `.gitignore`).        | Repository walk   |
| `project`   | PROJECT         | Project configuration and languages.                     | `project.yaml`    |
| `policy`    | POLICY          | Autonomy rules and gates.                                | `POLICY.yaml`     |
| `git`       | GIT             | Current branch and status.                               | `git status`      |
| `progress`  | PROGRESS        | History of actions in current session.                   | `progress.txt`    |
| `command`   | COMMAND         | Last executed shell command (for error recovery).        | `Executor` state  |
| `env`       | ENV             | Environment variables.                                   | `os.environ`      |

## Recursive Skills (Skills as Tools)

Blondie v2 supports recursive execution. A skill can be registered as a **Tool** that other skills (like the Orchestrator) can call - specifying `input-schema` provides tool interface and supplies input data, that can be referenced in the skill prompts by placeholders matching properties in the `input-schema`.

To make a skill callable as a tool:

1. Define an `input-schema` in the frontmatter. This defines the arguments the parent agent must provide.
2. (Optional) Define an `output-schema` to structure the return value.
3. Reference input properties in the skill's system prompt or in `user-content`.

**Example `input-schema`:**

```yaml
input-schema:
  type: object
  properties:
    error_log: {type: string}
  required: [error_log]
```

When the Orchestrator calls this skill, `LLMRouter` starts a new sub-session for this skill, injecting context and executing its tool loop, then returns the result to the Orchestrator.

## Tools

Skills can be equipped with tools defined in `src/agent/tooled.py` or other skills.

**Common Tools:**

* `run_shell`: Execute shell commands.
* `read_file`: Read file content.
* `write_file`: Write content to file.
* `pick_task`, `finalize_task`: Task lifecycle management.
* `run_tests`: Execute test suite.
