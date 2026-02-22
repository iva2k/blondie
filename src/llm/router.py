# src/llm/router.py

"""LLM Router - selects provider/model per task type."""

from pathlib import Path

import yaml
from rich.console import Console

from agent.policy import Policy
from llm.client import AnthropicClient, LLMClient, LLMResponse, OpenAIClient

console = Console()


class LLMRouter:
    """Smart LLM router with cost tracking and policy gating."""

    def __init__(self, secrets_path: Path, policy: Policy):
        self.policy = policy
        self.secrets = self._load_secrets(secrets_path)
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

        # OpenAI-compatible
        if "openai" in llm_secrets:
            cfg = llm_secrets["openai"]
            self.clients["openai"] = OpenAIClient(
                api_key=cfg["api_key"],
                base_url=cfg.get("api_base", "https://api.openai.com"),
                model=cfg.get("model", "gpt-4o-mini")
            )

        # Anthropic Claude
        if "anthropic" in llm_secrets:
            cfg = llm_secrets["anthropic"]
            self.clients["anthropic"] = AnthropicClient(
                api_key=cfg["api_key"],
                base_url=cfg.get("api_base", "https://api.anthropic.com"),
                model=cfg.get("model", "claude-3-5-sonnet-20240620")
            )

        console.print(f"🧠 LLM providers: {list(self.clients.keys())}")

    def select_model(self, operation: str) -> str:
        """Select best provider/model for operation."""
        model_map = {
            "planning": "anthropic",     # Reasoning
            "coding": "openai",          # Speed
            "debugging": "anthropic",    # Analysis
            "review": "anthropic",       # Quality
        }
        return model_map.get(operation, "openai")

    async def plan_task(
        self,
        task_title: str,
        repo_context: str,
        policy_summary: dict,
        **_kwargs
    ) -> LLMResponse:
        """Generate detailed implementation plan."""
        provider = self.select_model("planning")
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

        response = await client.chat(messages, temperature=0.1, max_tokens=2000)
        self.daily_cost += response.cost_usd

        console.print(f"📋 [{provider.upper()}] Plan: {response.tokens_used}t")
        return response

    async def generate_code(
        self,
        filename: str,
        existing_content: str,
        instruction: str,
        **_kwargs
    ) -> LLMResponse:
        """Generate/edit single file."""
        provider = self.select_model("coding")
        client = self.clients.get(provider)

        system_prompt = """You are expert code editor. Return ONLY full file content.

Rules:
• Preserve imports, structure, formatting
• Make minimal targeted changes  
• Include tests if new feature
• Follow existing code style
"""

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content":
                        f"FILENAME: {filename}\n"
                        f"EXISTING: {existing_content}\n"
                        f"INSTRUCT: {instruction}"
            }
        ]

        response = await client.chat(messages, temperature=0.05, max_tokens=8000)
        self.daily_cost += response.cost_usd

        console.print(
            f"💾 [{provider.upper()}] {filename}: {response.tokens_used}t")
        return response

    async def debug_error(
        self,
        error_log: str,
        code_context: str,
        **_kwargs
    ) -> LLMResponse:
        """Suggest fix for test failures."""
        provider = self.select_model("debugging")
        client = self.clients.get(provider)

        messages = [
            {
                "role": "user",
                "content": 
                        f"TEST ERROR:\n{error_log}\n\n"
                        f"CODE:\n{code_context}\n\n"
                        "Suggest targeted fix:"
            }
        ]

        response = await client.chat(messages, temperature=0.2, max_tokens=1500)
        self.daily_cost += response.cost_usd
        return response

    def check_daily_limit(self) -> bool:
        """Check cost limit from policy."""
        limit = getattr(self.policy.limits, "max_daily_cost_usd", float("inf"))
        if self.daily_cost > limit:
            console.print(f"💰 Daily limit exceeded: ${self.daily_cost:.2f}")
            return False
        return True

    async def close(self) -> None:
        """Cleanup HTTP clients."""
        for client in self.clients.values():
            await client.close()
