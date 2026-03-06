# Blondie Architecture v1: Procedural Loop

**Status**: Current (Stable)
**Implementation**: `src/agent/loop.py`

## 1. Overview

Blondie v1 operates as a rigid, Python-driven state machine. The control flow is defined explicitly in code, orchestrating LLM calls ("Skills") and local execution (Shell/Git) in a linear sequence with specific retry loops.

## 2. Core Components

- **Agent Loop (`loop.py`)**: The main entry point and controller. Manages the lifecycle of a task.
- **LLM Router (`router.py`)**: Handles communication with LLM providers (OpenAI/Anthropic).
- **Tool Handler (`tooled.py`)**: Intercepts tool calls from the LLM (e.g., `run_shell`, `read_file`) and executes them locally.
- **Context Gatherer (`context.py`)**: Collects relevant info (files, policy, task) to inject into LLM prompts.
- **Executor (`executor.py`)**: Wraps shell command execution with timeouts and policy gates.

## 3. Execution Flow

The `run_once()` method in `BlondieAgent` follows these steps:

1. **Task Selection**:
   - Checks `TASKS.md` for the next high-priority task.
   - Creates a git branch `task-ID`.

2. **Planning Phase**:
   - **Skill**: `plan_task`
   - **Interaction**: The LLM uses tools (`run_shell`, `read_file`) to explore the codebase.
   - **Output**: A Markdown plan.

3. **Architecture Phase**:
   - **Skill**: `get_file_edits`
   - **Input**: The plan from step 2.
   - **Output**: A structured YAML list of file operations (create, edit, delete) and shell commands.

4. **Coding Phase**:
   - Iterates through the YAML list.
   - **Skill**: `generate_code` (called for each file).
   - **Action**: Writes content directly to the file system.

5. **Verification Phase**:
   - Runs project tests (`npm test`, `pytest`, etc.) defined in `project.yaml`.

6. **Debugging Loop (If Verification Fails)**:
   - **Skill**: `debug_error`
   - **Input**: Test `stdout`/`stderr`.
   - **Interaction**: LLM uses tools to investigate.
   - **Output**: A fix plan.
   - **Action**: Re-runs Architecture/Coding phases for the fix.
   - *Retries*: Repeats up to `max_test_retries` (defined in Policy).

7. **Completion**:
   - Git add/commit/push.
   - Updates `TASKS.md`.
   - Attempts Git merge to main.

## 4. Limitations

- **Context Rot**: The context is gathered fresh for each skill, but the "memory" of what happened in previous steps is limited to what is explicitly passed (e.g., the Plan).
- **Rigidity**: The agent cannot decide to "skip planning" or "write a test first". It must follow the hardcoded steps.
- **Error Handling**: If the Debug loop fails, the agent gives up on the task. It cannot fundamentally change its strategy (e.g., "This approach is wrong, let's re-plan").
