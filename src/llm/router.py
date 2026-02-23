# src/llm/router.py

"""LLM Router - selects provider/model per task type."""

from pathlib import Path

import yaml
from rich.console import Console

from agent.llm_config import LLMConfig
from agent.policy import Policy
from llm.client import AnthropicClient, LLMClient, LLMResponse, OpenAIClient

console = Console()


class LLMRouter:
    """Smart LLM router with cost tracking and policy gating."""

    def __init__(self, secrets_path: Path, config_path: Path, policy: Policy | None = None):
        self.policy = policy
        self.secrets = self._load_secrets(secrets_path)
        self.config = LLMConfig.from_file(config_path)
        self.clients: dict[str, LLMClient] = {}
        self.daily_cost = 0.0
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
                )  # TODO: (now) else: raise Error(...)

        console.print(f"🧠 LLM providers: {list(self.clients.keys())}")

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

    async def plan_task(
        self, task_title: str, repo_context: str, policy_summary: dict, **_kwargs
    ) -> LLMResponse:
        """Generate detailed implementation plan."""
        provider, model = self.select_model("planning")
        client = self.clients.get(provider)

        if not client:
            raise ValueError(f"No client for provider '{provider}'")

        system_prompt = f"""You are Blondie, autonomous coding agent.

REPO: Frontend web app (detect language/framework from context)
TASK: {task_title}
CONTEXT: {repo_context}
POLICY SUMMARY: {policy_summary}

Generate a 5-step implementation plan. Include:
1. Files to create/modify
2. Key code changes  
3. Test verification steps
4. Potential risks + mitigations

Format as clean Markdown."""

        messages = [{"role": "system", "content": system_prompt}]

        response = await client.chat(messages, temperature=0.1, max_tokens=2000, model=model)
        self.daily_cost += response.cost_usd

        console.print(f"📋 [{provider.upper()}] Plan: {response.tokens_used}t")
        return response

    async def get_file_edits(self, task_title: str, plan: str, **_kwargs) -> LLMResponse:
        """Identify files to edit from plan."""
        provider, model = self.select_model("planning")
        client = self.clients.get(provider)

        if not client:
            raise ValueError(f"No client for provider '{provider}'")

        system_prompt = """You are a coding architect.
Based on the TASK and PLAN, return a list of file operations.
Return ONLY a YAML list format. Example:

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
For shell actions:
- Use non-interactive flags (e.g. -y, --no-input) to prevent hanging.
- Specify a timeout in seconds (default 120) if the command is expected to be slow.
Do not include markdown formatting (like ```yaml), just the raw YAML text.
"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"TASK: {task_title}\nPLAN:\n{plan}"},
        ]

        response = await client.chat(messages, temperature=0.1, max_tokens=1000, model=model)
        self.daily_cost += response.cost_usd
        return response

    async def generate_code(
        self, filename: str, existing_content: str, instruction: str, **_kwargs
    ) -> LLMResponse:
        """Generate/edit single file."""
        provider, model = self.select_model("coding")
        client = self.clients.get(provider)

        if not client:
            raise ValueError(f"No client for provider '{provider}'")

        system_prompt = """You are expert code editor. Return ONLY full file content.

Rules:
• If creating a new file, provide complete implementation.
• If editing, preserve imports, structure, formatting, comments, docstrings.
• Make minimal targeted changes based on INSTRUCT.
• Include tests if new feature
• Follow existing code style
"""

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"FILENAME: {filename}\n"
                f"EXISTING: {existing_content}\n"
                f"INSTRUCT: {instruction}",
            },
        ]

        response = await client.chat(messages, temperature=0.05, max_tokens=8000, model=model)
        self.daily_cost += response.cost_usd

        console.print(f"💾 [{provider.upper()}] {filename}: {response.tokens_used}t")
        return response

    async def debug_error(self, error_log: str, code_context: str, **_kwargs) -> LLMResponse:
        """Suggest fix for test failures."""
        provider, model = self.select_model("debugging")
        client = self.clients.get(provider)

        if not client:
            raise ValueError(f"No client for provider '{provider}'")

        messages = [
            {
                "role": "user",
                "content": f"TEST ERROR:\n{error_log}\n\n"
                f"CODE:\n{code_context}\n\n"
                "Analyze the error and provide a step-by-step fix plan. "
                "Focus on the specific files that need changes.",
            }
        ]

        response = await client.chat(messages, temperature=0.2, max_tokens=1500, model=model)
        self.daily_cost += response.cost_usd
        return response

    def check_daily_limit(self) -> bool:
        """Check cost limit from policy."""
        if not self.policy:
            return True
        limit = self.policy.limits.get("max_daily_cost_usd", float("inf"))
        if self.daily_cost > limit:
            console.print(f"💰 Daily limit exceeded: ${self.daily_cost:.2f}")
            return False
        return True

    async def close(self) -> None:
        """Cleanup HTTP clients."""
        for client in self.clients.values():
            await client.close()
