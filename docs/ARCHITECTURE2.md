# Next-Gen Blondie Architecture: Recursive Skill Orchestration

**Status**: Proposal (Draft)
**Date**: 2026-03-04
**Related Tasks**: 058, 028, 056, 057, 054

## 1. Executive Summary

Current Blondie architecture relies on a rigid, procedural state machine (Plan → Architect → Code → Verify). While effective for linear tasks, this approach struggles with complex debugging loops, context rot, and adaptability.

The Next-Gen architecture proposes a **"Skills as Tools"** paradigm. Instead of a hard-coded loop, the main agent acts as an **Orchestrator** that calls other Skills (Planner, Coder, Debugger) as **Tools**.

This enables:

1. **Recursive Execution**: A skill can call other skills.
2. **Context Encapsulation**: Sub-tasks run in isolated contexts, preventing the main context from filling up with noise (e.g., `ls`, `cat` commands).
3. **Self-Correction**: The Orchestrator can observe a tool failure (e.g., Coder failed) and decide to call a different tool (e.g., Debugger) without a hard-coded "retry" logic.

## 2. Core Concepts

### 2.1. The Skill-Tool Pattern (Task 058, 056)

Currently, `skill.py` defines a prompt template. In the new architecture, a **Skill** is defined as:

1. **System Prompt**: The persona and instructions (existing).
2. **Input Schema**: A structured definition of arguments required to invoke this skill (New).
3. **Output Schema**: A structured definition of output format (Semi-New).
4. **Tool Definition**: An auto-generated interface allowing LLMs to call this skill as a function.

**Example Flow:**

1. **Orchestrator** receives a task.
2. Orchestrator decides it needs a plan and calls tool `plan_task(task_description="...")`.
3. The system handles this tool call. Instead of running a Python function, it spins up a **Sub-Agent** (ephemeral `ChatSession`).
4. The Sub-Agent executes the `plan_task` skill, potentially using its own tools (`read_file`, `grep`).
5. The Sub-Agent finishes and returns the final plan string.
6. The system returns this string as the "Tool Output" to the Orchestrator.

### 2.2. Context Isolation & Stack (Task 028, 057)

To solve "Context Rot" and "Nested Loop" issues:

- **The Stack**: Execution is a stack of `ChatSessions`.
- **Isolation**: The Orchestrator does not see the intermediate steps (tool calls) of the Sub-Agent. It only sees the input (Task) and the output (Result).
- **Benefit**: If the `debug_error` skill takes 50 turns to find a missing semicolon, the Orchestrator's context only grows by 1 turn (The call and the fix).

### 2.3. Summarized Restart (Task 054, 057)

If a Sub-Agent hits a token limit or gets stuck:

1. It triggers a `summarize_and_restart` action.
2. The system condenses the current session history into a "Knowledge Summary".
3. The session is wiped, and a new session starts with the original System Prompt + Knowledge Summary.

## 3. Component Architecture

### 3.1. Enhanced Skill Definition (`src/llm/skill.py`)

Skills will use extended Frontmatter to define their tool interface.

```yaml
---
name: generate_code
description: Generate or edit a file.
input_schema:
  type: object
  properties:
    filename: {type: string}
    instruction: {type: string}
    existing_content: {type: string}
  required: [filename, instruction]
output_schema:
  type: object
  properties:
    TBD
  required: [TBD]
context: [task, plan, project, policy]  # Legacy context auto-gatherer options. TBD if useful in this implementation.
tools: [run_shell, read_file] # Tools this skill can use internally
user-content: ""  # Legacy user prompt template
---
# ... the system prompt template
```

### 3.2. Dynamic Tool Registry (src/agent/tooled.py)

The `ToolHandler` will no longer rely solely on hardcoded `TOOL_DEFINITIONS`.

- **Registry**: A dynamic dictionary mapping `tool_name` → `Executable`.
- **Skill Adapter**: A wrapper that converts a `Skill` object into a callable tool that spawns a `ChatSession`.

### 3.3. Recursive Router (src/agent/router.py)

The `LLMRouter` needs to support nested sessions.

- execute_tool_call(call):
  - If tool is "primitive" (shell, file): Execute directly.
  - If tool is "skill" (planner, coder):
    1. Instantiate new ChatSession with that Skill's prompt.
    2. Inject arguments from the tool call into the session context.
    3. Run the session until it produces a "Final Answer" or "Return" signal.
    4. Return that result to the parent session.

## 4. Migration Strategy

### Phase 1: Toolify Skills (Task 058)

- Update `Skill` class to parse `input_schema`.
- Generate OpenAI/Anthropic tool definitions from `Skill` objects.

### Phase 2: The Orchestrator

- Create a new root skill: `orchestrator.skill.md`.
- Give it access to `plan_task`, `generate_code`, `debug_error` as tools.

### Phase 3: Recursive Runtime

- Refactor `router.py` to handle the "Skill-as-Tool" execution flow.
- Implement the Context Stack.

## 5. Workflow Comparison

| Feature       | Current (v1)            | Next-Gen (v2)                 |
|---------------|-------------------------|-------------------------------|
| Control Flow  | Python Code (`loop.py`) | LLM (`orchestrator` skill)    |
| Context       | Shared/Global           | Stacked/Isolated              |
| Tooling       | Hardcoded (Shell/File)  | Dynamic (Skills + Primitives) |
| Debugging     | Linear Retry Loop       | Intelligent Sub-Agent Call    |
| Extensibility | Modify Python Code      | Add `.skill.md` file          |

## 6. Open Questions

- **Cost Control**: Recursive agents can burn tokens fast. We need strict budget passing (e.g., "You have $0.50 for this sub-task").
- **Infinite Loops**: The Orchestrator might keep calling debug_error forever. We need a "Supervisor" or "Max Depth/Retry" policy enforced by the runtime.
