# src/llm/router.py

"""LLM Router - selects provider/model per task type."""

import datetime
from pathlib import Path

import yaml

from agent.llm_config import LLMConfig
from agent.policy import Policy
from llm.client import AnthropicClient, LLMClient, LLMResponse, OpenAIClient
from llm.journal import Journal
from llm.skill import Skill


class LLMRouter:
    """Smart LLM router with cost tracking and policy gating."""

    def __init__(
        self,
        secrets_path: Path,
        config_path: Path,
        policy: Policy | None = None,
        journal: Journal | None = None,
        skills_dir: Path | None = None,
    ):
        self.policy = policy
        self.journal = journal or Journal()
        self.secrets = self._load_secrets(secrets_path)
        self.config = LLMConfig.from_file(config_path)
        self.clients: dict[str, LLMClient] = {}
        self.daily_cost = 0.0
        self.last_reset_date = datetime.date.today()

        # Load skills
        if skills_dir is None:
            # Default to root/skills relative to this file
            skills_dir = Path(__file__).parents[2] / "skills"
        self.skills = self._load_skills(skills_dir)

        self._init_clients()

    def _load_secrets(self, secrets_path: Path) -> dict:
        """Load secrets.env.yaml."""
        if not secrets_path.exists():
            raise FileNotFoundError(f"Missing {secrets_path}")

        with secrets_path.open("r") as f:
            return yaml.safe_load(f) or {}

    def _load_skills(self, skills_dir: Path) -> dict[str, Skill]:
        skills = {}
        if not skills_dir.exists():
            self.journal.print(f"⚠️ Skills directory not found: {skills_dir}")
            return skills

        for path in skills_dir.glob("*.md"):
            try:
                skill = Skill.from_file(path)
                skills[skill.name] = skill
            except Exception as e:
                self.journal.print(f"❌ Failed to load skill {path.name}: {e}")
        return skills

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
        skill = self.skills["plan_task"]
        system_prompt = skill.render_system_prompt(
            task_title=task_title,
            repo_context=repo_context,
            policy_summary=policy_summary,
        )

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
        skill = self.skills["get_file_edits"]
        system_prompt = skill.render_system_prompt()

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
        skill = self.skills["generate_code"]
        system_prompt = skill.render_system_prompt()

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
        skill = self.skills["debug_error"]
        system_prompt = skill.render_system_prompt()

        user_content = f"TEST ERROR:\n{error_log}\n\nCONTEXT:\n{code_context}"

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
