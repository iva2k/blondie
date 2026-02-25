# src/llm/router.py

"""LLM Router - selects provider/model per task type."""

import datetime
from pathlib import Path

import yaml

from agent.llm_config import LLMConfig
from agent.policy import Policy
from llm.client import AnthropicClient, LLMClient, LLMResponse, OpenAIClient
from llm.journal import Journal

AGENT_FLOW = """
1. Plan: Analyze task and design solution (CURRENT STEP). Output: Markdown plan.
2. Architect: Determine file operations. Output: YAML list of actions.
3. Code Gen: Generate content for specific files. Output: Full file content.
4. Verify: Run tests.
5. Debug: Fix errors if verification fails.
6. Commit: System commits changes. (Do NOT run git commands manually).
"""


class LLMRouter:
    """Smart LLM router with cost tracking and policy gating."""

    def __init__(
        self, secrets_path: Path, config_path: Path, policy: Policy | None = None, journal: Journal | None = None
    ):
        self.policy = policy
        self.journal = journal or Journal()
        self.secrets = self._load_secrets(secrets_path)
        self.config = LLMConfig.from_file(config_path)
        self.clients: dict[str, LLMClient] = {}
        self.daily_cost = 0.0
        self.last_reset_date = datetime.date.today()
        self._init_clients()

    def _load_secrets(self, secrets_path: Path) -> dict:
        """Load secrets.env.yaml."""
        if not secrets_path.exists():
            raise FileNotFoundError(f"Missing {secrets_path}")

        with secrets_path.open("r") as f:
            return yaml.safe_load(f) or {}

    def _init_clients(self) -> None:
        """Initialize available LLM providers."""
        llm_secrets = self.secrets.get("llm", {})

        for name, provider_cfg in self.config.providers.items():
            secret = llm_secrets.get(name)
            if not secret:
                continue

            api_key = secret.get("api_key")
            if not api_key:
                continue

            if provider_cfg.api_type == "openai":
                self.clients[name] = OpenAIClient(
                    api_key=api_key,
                    base_url=provider_cfg.base_url or "https://api.openai.com/v1",
                    model=provider_cfg.default_model or "gpt-4o-mini",
                )
            elif provider_cfg.api_type == "anthropic":
                self.clients[name] = AnthropicClient(
                    api_key=api_key,
                    base_url=provider_cfg.base_url or "https://api.anthropic.com/v1",
                    model=provider_cfg.default_model or "claude-3-5-sonnet-20240620",
                )
            else:
                raise ValueError(f"Unknown LLM provider type: {provider_cfg.api_type}")

        self.journal.print(f"🧠 LLM providers: {list(self.clients.keys())}")

    def select_model(self, operation: str) -> tuple[str, str | None]:
        """Select best provider/model for operation based on config priority."""
        selections = self.config.operations.get(operation, [])

        for selection in selections:
            if selection.provider in self.clients:
                return selection.provider, selection.model

        # Fallback: return first available client
        if self.clients:
            return list(self.clients.keys())[0], None

        raise ValueError(f"No active LLM provider found for operation '{operation}'")

    async def _execute_llm_task(
        self,
        operation: str,
        system_prompt: str,
        user_prompt: str | None,
        temperature: float,
        max_tokens: int,
        log_action: str,
        log_title: str,
    ) -> LLMResponse:
        """Execute LLM task with common logging and cost tracking."""
        provider, model = self.select_model(operation)
        client = self.clients.get(provider)

        if not client:
            raise ValueError(f"No client for provider '{provider}'")

        messages = [{"role": "system", "content": system_prompt}]
        if user_prompt:
            messages.append({"role": "user", "content": user_prompt})

        response = await client.chat(messages, temperature=temperature, max_tokens=max_tokens, model=model)
        self.daily_cost += response.cost_usd
        self.journal.log_chat(
            log_action,
            provider,
            log_title,
            response,
            system_prompt=system_prompt,
            model=client.model,
            endpoint=client.base_url,
        )
        return response

    async def plan_task(self, task_title: str, repo_context: str, policy_summary: dict, **_kwargs) -> LLMResponse:
        """Generate detailed implementation plan."""
        system_prompt = f"""You are Blondie, an autonomous coding agent.
You are planning changes for a software repository.
Your output will be used by another LLM to generate specific file edits and shell commands.

You Are at step 1 of AGENT FLOW.

AGENT FLOW: {AGENT_FLOW}

TASK: {task_title}
POLICY SUMMARY: {policy_summary}
CONTEXT: {repo_context}

Instructions:
1. Generate implementation plan.
2. Use specific file paths (relative to repo root).
3. Do NOT use placeholders like <project_name> or <date>. Use actual values or sensible defaults.
4. Do NOT provide human-centric instructions like "Open file", "Navigate to".
5. For shell commands, use exact flags for non-interactive execution (e.g. -y, --no-input).
6. Standard shell commands (grep, find, etc.) are allowed per POLICY.
7. For package version resolution, instruct to use internet query (e.g. npm view, pip index) to get latest versions.

Format as clean Markdown with these sections:
1. **Shell Commands to Initialize**: List of commands to prepare project (scaffolding).
2. **Files to Create/Modify**: List of files.
3. **Shell Commands**: List of commands to run (install dependencies, etc).
4. **Code Changes**: Detailed description of logic changes.
5. **Verification**: Automated tests to run (e.g. `pytest tests/test_foo.py`). Do not list manual steps.
6. **Risks**: Potential risks + mitigations."""

        return await self._execute_llm_task(
            operation="planning",
            system_prompt=system_prompt,
            user_prompt=None,
            temperature=0.1,
            max_tokens=2000,
            log_action="plan_task",
            log_title=f"Task: {task_title}",
        )

    async def get_file_edits(self, task_title: str, plan: str, context: str = "", **_kwargs) -> LLMResponse:
        """Identify files to edit from plan."""
        system_prompt = f"""You are a coding architect.

You Are at step 2 of AGENT FLOW.

AGENT FLOW: {AGENT_FLOW}

Based on the TASK and PLAN, return a list of file operations.
Return ONLY a YAML list format.

Rules:
1. Use specific file paths relative to repo root. Check CONTEXT for existing file structure.
2. For 'edit' actions, the instruction must be a clear directive for a code generator (e.g. "Add function X", "Update import Y").
3. Do NOT use human instructions like "Open file" or "Locate line".
4. For 'shell' actions, provide the exact command string.
   - MUST use non-interactive flags (e.g. -y, --no-input, --batch).
   - Do NOT use placeholders.
   - Specify timeout in seconds if needed.
   - Standard bash tools (grep, find, cat) are allowed.

Example:

- path: src/main.py
  action: edit
  instruction: Add login function
- path: tests/test_main.py
  action: create
  instruction: Add unit tests for login
- action: shell
  command: npm install axios
  timeout: 300
- path: old_file.py
  action: delete

Valid actions: create, edit, delete, shell.
Do not include markdown formatting (like ```yaml), just the raw YAML text.
"""
        user_content = f"TASK: {task_title}\nPLAN:\n{plan}"
        if context:
            user_content = f"CONTEXT:\n{context}\n\n{user_content}"

        return await self._execute_llm_task(
            operation="planning",
            system_prompt=system_prompt,
            user_prompt=user_content,
            temperature=0.1,
            max_tokens=1000,
            log_action="get_file_edits",
            log_title=f"Task: {task_title}",
        )

    async def generate_code(
        self, filename: str, existing_content: str, instruction: str, context: str = "", **_kwargs
    ) -> LLMResponse:
        """Generate/edit single file."""
        system_prompt = f"""You are an expert code editor.

You Are at step 3 of AGENT FLOW.

AGENT FLOW: {AGENT_FLOW}

Your task is to output the FULL content of the file based on the INSTRUCTION.

Rules:
• Return ONLY the file content. No markdown fences, no explanations.
• If creating a new file, provide complete implementation.
• If editing, you must output the COMPLETE file with changes applied.
• Preserve imports, structure, formatting, comments, docstrings (unless instructed to change).
• CRITICAL: You must output the ENTIRE file content. Do not omit any parts. Do not use comments like `# ... existing code ...`.
• Do NOT use placeholders for variable names or config values.
• Ensure code is syntactically correct and follows the repo's style.
"""

        user_content = f"FILENAME: {filename}\nEXISTING: {existing_content}\nINSTRUCTION: {instruction}"
        if context:
            user_content += f"\nCONTEXT:\n{context}"

        return await self._execute_llm_task(
            operation="coding",
            system_prompt=system_prompt,
            user_prompt=user_content,
            temperature=0.05,
            max_tokens=8000,
            log_action="generate_code",
            log_title=f"File: {filename}\nInstruction: {instruction}",
        )

    async def debug_error(self, error_log: str, code_context: str, **_kwargs) -> LLMResponse:
        """Suggest fix for test failures."""
        system_prompt = f"""You are an autonomous debugging assistant.

You Are at step 5 of AGENT FLOW.

AGENT FLOW: {AGENT_FLOW}

Your goal is to fix the error."""

        user_content = (
            f"TEST ERROR:\n{error_log}\n\n"
            f"CONTEXT:\n{code_context}\n\n"
            "Analyze the error and provide a fix plan.\n"
            "Rules:\n"
            "1. Focus on specific files to edit.\n"
            "2. Provide concrete instructions for code changes.\n"
            "3. Do NOT use human steps like 'Open file'.\n"
            "4. If a shell command is needed (e.g. install missing package, grep for error), specify it exactly with non-interactive flags."
        )

        return await self._execute_llm_task(
            operation="debugging",
            system_prompt=system_prompt,
            user_prompt=user_content,
            temperature=0.2,
            max_tokens=1500,
            log_action="debug_error",
            log_title=f"Error: {error_log}",
        )

    def check_daily_limit(self) -> bool:
        """Check cost limit from policy."""
        if datetime.date.today() > self.last_reset_date:
            self.daily_cost = 0.0
            self.last_reset_date = datetime.date.today()
            self.journal.print("🔄 Daily cost reset for new day.")

        if not self.policy:
            return True
        limit = self.policy.limits.get("max_daily_cost_usd", float("inf"))
        if self.daily_cost > limit:
            self.journal.print(f"💰 Daily limit exceeded: ${self.daily_cost:.2f}")
            return False
        return True

    async def close(self) -> None:
        """Cleanup HTTP clients."""
        for client in self.clients.values():
            await client.close()
