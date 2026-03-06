# Next-Gen Blondie Architecture: Recursive Skill Orchestration

**Status**: Proposal (Draft)
**Date**: 2026-03-04
**Related Tasks**: 058, 028, 056, 057, 054

## 1. Executive Summary

Current Blondie architecture (v1) relies on a rigid, procedural state machine (`src/agent/loop.py`) implementing the Plan → Architect → Code → Verify cycle. While effective for linear tasks, this approach struggles with complex debugging loops, context rot, and adaptability.

The Next-Gen architecture (v2) proposes a **"Skills as Tools"** paradigm implemented in a new module `src/agent/loop2.py`. Instead of a hard-coded loop, the main agent acts as an **Orchestrator** that calls other Skills (Planner, Coder, Debugger) as **Tools**.

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

### 2.4. Data Flow & Side Effects (Optimization)

To prevent context bloat in the Orchestrator, we adopt an **"Action over Data Transfer"** principle.

- **Problem**: If `generate_code` returns the full file content to the Orchestrator, the Orchestrator's context fills up with code it doesn't need to read, just to pass it to a `write_file` tool.
- **Solution**: Skills should be side-effect heavy. The `generate_code` skill should use a `write_file` tool *internally* to apply changes and return a concise summary (e.g., "Updated src/main.py") to the Orchestrator.
- **Pattern - Pass References, Not Values**:
  - Large Data (Code, Plans) -> File System.
  - Small Data (Status, Paths) -> LLM Context.
  - *Example*: `plan_task` writes `docs/plan.md` and returns "Plan saved to docs/plan.md". The Orchestrator passes that path to `generate_code`.
- **Implication**:
  - We need a primitive `write_file` tool available to Sub-Agents.
  - Skill prompts must be updated to prefer tool usage over returning content.
  - The Orchestrator acts as a manager (delegating tasks), not a pipe (moving data).

## 3. Component Architecture

### 3.1. Enhanced Skill Definition (`src/llm/skill.py`)

**Strategy**: Incremental Edit.

Skills will use extended Frontmatter to define their tool interface. Existing `Skill` class will be updated to parse these new fields without breaking existing skills.
If `output_schema` is present, `Skill.render_system_prompt` will automatically append a `## Output Format` section containing the JSON schema and instructions, ensuring consistent LLM output without manual prompt engineering.

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

### 3.2. Dynamic Tool Registry (`src/agent/tooled.py`)

**Strategy**: Incremental Edit.

The `ToolHandler` will be updated to support a dynamic registry of tools, merging the existing hardcoded primitives (`run_shell`, `read_file`, `write_file`) with dynamically loaded Skill-Tools.

- **Registry**: A dynamic dictionary mapping `tool_name` → `Executable`.
- **Skill Adapter**: A wrapper that converts a `Skill` object into a callable tool that spawns a `ChatSession`.

### 3.3. Recursive Router (`src/agent/router.py`)

**Strategy**: Incremental Edit.

The `LLMRouter` will be enhanced to support nested sessions. This allows a `ChatSession` to pause, execute a Skill-Tool (which spins up a child `ChatSession`), and resume with the result.

- execute_tool_call(call):
  - **Validation**: If the skill has an `output_schema`, the router validates the final response against this JSON schema before returning.
  - If tool is "primitive" (shell, file): Execute directly.
  - If tool is "skill" (planner, coder):
    1. Instantiate new ChatSession with that Skill's prompt.
    2. Inject arguments from the tool call into the session context.
    3. Run the session until it produces a "Final Answer" or "Return" signal.
    4. Return that result to the parent session.
    5. **Context Refresh**: Upon return, the parent session triggers a refresh of its `ContextGatherer` (e.g., re-listing files) to reflect changes made by the child.

### 3.4. The Orchestrator (`src/agent/loop2.py`)

**Strategy**: New Module.

A new entry point that replaces `loop.py` for v2 execution. It initializes the root `orchestrator` skill and manages the top-level execution flow, delegating actual work to the recursive router.

### 3.5. System Tools (Hardcoded)

To allow the Orchestrator to manage the lifecycle without reimplementing logic in prompts, we will expose existing Python logic as tools. These remain hardcoded in Python but are callable by the LLM:

- **Task Management**: `get_next_task`, `claim_task`, `complete_task` (wraps `TasksManager`).
- **Git Operations**: `git_checkout`, `git_commit`, `git_push`, `git_merge` (wraps `GitCLI`).
- **Execution**: `run_tests` (wraps `Executor.run_tests`).
- **State**: `check_daily_limit` (wraps `LLMRouter`).

These tools allow the Orchestrator to say (by tool calls) "I am done, mark task complete" or "I need to start working on task X".

### 3.6. Observability

Recursive execution requires hierarchical logging.

- **Journal**: Needs to support `start_span(name)` and `end_span()`.
- **Router/ToolHandler**: Must track execution depth/parent ID and pass it to the Journal to maintain the trace tree.
- **Output**: Logs should be indented or visually grouped to distinguish between the Orchestrator's thoughts and a Sub-Agent's thoughts, and sub-sub-agents.

## 4. Migration Strategy

### Phase 1: Infrastructure Enhancements (Incremental)

- Update `Skill` class in `skill.py` to parse `input_schema`.
- Update `ToolHandler` in `tooled.py` to support dynamic tool registration.

### Phase 2: The Orchestrator (New Module)

- Create `src/agent/loop2.py` implementing the Orchestrator pattern.
- **Implement System Tools**: Wrap `TasksManager`, `GitCLI`, and `Executor` methods into tools in `tooled.py`.
- Create `orchestrator.skill.md` with access to `plan_task`, `generate_code`, `debug_error` as tools.

### Phase 3: Recursive Runtime (Incremental)

- Enhance `router.py` to handle the "Skill-as-Tool" execution flow via recursion.
- Implement the Context Stack.

## 5. Workflow Comparison

| Feature       | Current (v1)            | Next-Gen (v2)                 |
|---------------|-------------------------|-------------------------------|
| Control Flow  | Python Code (`loop.py`) | LLM (`loop2.py` + `orchestrator` skill) |
| Context       | Shared/Global           | Stacked/Isolated              |
| Tooling       | Hardcoded (Shell/File)  | Dynamic (Skills + Primitives) |
| Debugging     | Linear Retry Loop       | Intelligent Sub-Agent Call    |
| Extensibility | Modify Python Code      | Add `.skill.md` file          |

## 6. Open Questions

- **Cost Control**: Recursive agents can burn tokens fast. We need strict budget passing (e.g., "You have $0.50 for this sub-task").
- **Infinite Loops**: The Orchestrator might keep calling debug_error forever. We need a "Supervisor" or "Max Depth/Retry" policy enforced by the runtime.
