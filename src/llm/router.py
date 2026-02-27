# src/llm/router.py

"""LLM Router - selects provider/model per task type."""

import datetime
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import ValidationError

from agent.context import ContextGatherer
from agent.llm_config import LLMConfig
from agent.policy import Policy
from llm.client import AnthropicClient, LLMClient, LLMResponse, OpenAIClient
from llm.journal import Journal
from llm.skill import Skill
from llm.tooled import TOOL_DEFINITIONS


class ChatSession:
    """Stateful chat session for multi-turn conversations."""

    def __init__(
        self,
        client: LLMClient,
        provider_name: str,
        model: str | None,
        journal: Journal,
        cost_callback: Callable[[float], None],
        system_prompt: str,
        temperature: float,
        max_tokens: int,
        log_action: str,
        log_title: str,
        response_schema: Any | None = None,
        response_format: Literal["json", "yaml"] | None = None,
        tools: list[dict[str, Any]] | None = None,
    ):
        self.client = client
        self.provider_name = provider_name
        self.journal = journal
        self.cost_callback = cost_callback
        self.system_prompt = system_prompt
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.log_action = log_action
        self.log_title = log_title
        self.response_schema = response_schema
        self.response_format = response_format
        self.tools = tools

        self.messages: list[dict[str, Any]] = [{"role": "system", "content": self.system_prompt}]

    async def send(
        self,
        prompt: str | None = None,
        response_schema: Any | None = None,
        response_format: Literal["json", "yaml"] | None = None,
    ) -> LLMResponse:
        """Send message to LLM and get response."""
        if prompt:
            self.messages.append({"role": "user", "content": prompt})

        # Defaults from session if not provided
        use_response_schema = response_schema or self.response_schema
        use_response_format = response_format or self.response_format

        max_retries = 3 if use_response_schema else 0
        attempts = 0

        while True:
            attempts += 1

            # Call LLM
            response = await self.client.chat(
                self.messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                model=self.model,
                tools=self.tools,
            )

            # Track cost
            self.cost_callback(response.cost_usd)

            # Log
            turn = sum(1 for m in self.messages if m["role"] == "user")
            log_suffix = ""
            if turn > 1 or attempts > 1:
                log_suffix += f" (Turn {turn}" + (f" Attempt {attempts})" if attempts > 1 else ")")
            if self.messages:
                log_suffix += f": {len(self.messages)} messages"

            prompt_content = ""
            if self.messages:
                last_msg = self.messages[-1]
                if last_msg.get("role") == "user":
                    prompt_content = str(last_msg.get("content", ""))

            self.journal.log_chat(
                self.log_action,
                self.provider_name,
                prompt_content,
                response,
                system_prompt=self.system_prompt,
                model=self.client.model,
                endpoint=self.client.base_url,
                title=self.log_title + log_suffix,
            )

            # If tool calls, append to history and return (caller handles execution)
            if response.tool_calls:
                msg = {"role": "assistant", "content": response.content, "tool_calls": response.tool_calls}
                self.messages.append(msg)
                return response

            # If no validation needed, we are done
            if not use_response_schema and not use_response_format:
                self.messages.append({"role": "assistant", "content": response.content})
                return response

            # Validation
            try:
                content_str = response.content.strip()
                # Handle markdown code blocks
                if content_str.startswith("```"):
                    lines = content_str.splitlines()
                    if lines and lines[0].startswith("```"):
                        lines = lines[1:]
                    if lines and lines[-1].strip() == "```":
                        lines = lines[:-1]
                    content_str = "\n".join(lines).strip()

                data = None
                if use_response_format == "json":
                    data = json.loads(content_str)
                elif use_response_format == "yaml":
                    data = yaml.safe_load(content_str)

                if data is not None:
                    response.parsed = data

                if use_response_schema and hasattr(use_response_schema, "model_validate"):
                    validated = use_response_schema.model_validate(data)
                    response.parsed = validated

                self.messages.append({"role": "assistant", "content": response.content})
                return response

            except (json.JSONDecodeError, yaml.YAMLError, ValidationError) as e:
                if attempts > max_retries:
                    self.journal.print(f"❌ Validation failed after {max_retries} retries: {e}")
                    self.messages.append({"role": "assistant", "content": response.content})
                    return response

                self.journal.print(f"⚠️ Validation failed (Attempt {attempts}/{max_retries + 1}): {e}")

                self.messages.append({"role": "assistant", "content": response.content})
                self.messages.append(
                    {
                        "role": "user",
                        "content": f"Error parsing response: {e}\nPlease return valid {str(use_response_format).upper()} matching the schema.",
                    }
                )

    def add_tool_result(self, tool_call_id: str, output: str) -> None:
        """Add a tool execution result to the history."""
        self.messages.append(
            {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": output,
            }
        )


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
        skills: dict[str, Skill] = {}
        if not skills_dir.exists():
            self.journal.print(f"⚠️ Skills directory not found: {skills_dir}")
            return skills

        for path in skills_dir.glob("*.md"):
            try:
                skill = Skill.from_file(path)
                skills[skill.name] = skill
            # pylint: disable-next=broad-exception-caught
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

    def _track_cost(self, cost: float) -> None:
        self.daily_cost += cost

    async def _execute_llm_task(
        self,
        operation: str,
        system_prompt: str,
        user_prompt: str | None,
        temperature: float,
        max_tokens: int,
        log_action: str,
        log_title: str,
        response_schema: Any | None = None,
        response_format: Literal["json", "yaml"] | None = None,
    ) -> LLMResponse:
        """Execute LLM task with common logging and cost tracking."""
        provider, model = self.select_model(operation)
        if provider not in self.clients:
            raise ValueError(f"Provider '{provider}' not configured")

        session = ChatSession(
            client=self.clients[provider],
            provider_name=provider,
            model=model,
            journal=self.journal,
            cost_callback=self._track_cost,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            log_action=log_action,
            log_title=log_title,
            response_schema=response_schema,
            response_format=response_format,
        )

        return await session.send(prompt=user_prompt)

    async def _execute_llm_skill(
        self, skill_name: str, context_gatherer: ContextGatherer, **kwargs: Any
    ) -> LLMResponse:
        """Generate detailed implementation plan."""
        if skill_name not in self.skills:
            raise ValueError(f"Skill not found: {skill_name}")
        skill = self.skills[skill_name]
        response_schema = kwargs.pop("response_schema", None) or skill.response_schema
        response_format = kwargs.pop("response_format", None) or skill.response_format
        kwargs = kwargs or {}
        if context_gatherer:
            context_str, context_parts = context_gatherer.gather(skill.context)
            kwargs["context"] = context_str
            kwargs.update(context_parts)
        system_prompt = skill.render_system_prompt(**kwargs)
        user_content = skill.user_content.format(**kwargs) if skill.user_content else ""
        log_title = skill.log_title.format(**kwargs) if skill.log_title else ""
        response = await self._execute_llm_task(
            operation=skill.operation,
            system_prompt=system_prompt,
            user_prompt=user_content,
            temperature=skill.temperature,
            max_tokens=skill.max_tokens,
            log_action=skill_name,
            log_title=log_title,
            response_schema=response_schema,
            response_format=response_format,
        )

        if "Missing CONTEXT sections:" in response.content:
            raise ValueError(f"Skill '{skill_name}' configuration error: {response.content.strip()}")

        return response

    async def plan_task(
        self, context_gatherer: ContextGatherer, task_title: str, policy_summary: str, **kwargs: Any
    ) -> LLMResponse:
        """Generate detailed implementation plan."""
        return await self._execute_llm_skill(
            "plan_task",
            context_gatherer,
            task_title=task_title,
            policy_summary=policy_summary,
            **kwargs,
        )

    async def get_file_edits(
        self, context_gatherer: ContextGatherer, task_title: str, user_plan: str, **kwargs: Any
    ) -> LLMResponse:
        """Identify files to edit from plan."""
        return await self._execute_llm_skill(
            "get_file_edits",
            context_gatherer,
            task_title=task_title,
            user_plan=user_plan,
            **kwargs,
        )

    async def generate_code(
        self,
        context_gatherer: ContextGatherer,
        task_title: str,
        filename: str,
        existing_content: str,
        instruction: str,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate/edit single file."""
        return await self._execute_llm_skill(
            "generate_code",
            context_gatherer,
            task_title=task_title,
            filename=filename,
            existing_content=existing_content,
            instruction=instruction,
            **kwargs,
        )

    async def debug_error(
        self, context_gatherer: ContextGatherer, task_title: str, error_log: str, **kwargs: Any
    ) -> LLMResponse:
        """Suggest fix for test failures."""
        return await self._execute_llm_skill(
            "debug_error",
            context_gatherer,
            task_title=task_title,
            error_log=error_log,
            **kwargs,
        )

    def start_chat(
        self, skill_name: str, context_gatherer: ContextGatherer | None = None, **kwargs: Any
    ) -> ChatSession:
        """Start a multi-turn chat session."""
        if skill_name not in self.skills:
            raise ValueError(f"Skill not found: {skill_name}")
        skill = self.skills[skill_name]

        if context_gatherer:
            context_str, context_parts = context_gatherer.gather(skill.context)
            kwargs["context"] = context_str
            kwargs.update(context_parts)

        system_prompt = skill.render_system_prompt(**kwargs)
        provider, model = self.select_model(skill.operation)
        if provider not in self.clients:
            raise ValueError(f"Provider '{provider}' not configured")

        log_title = skill.log_title.format(**kwargs) if skill.log_title else skill.name

        tools = []
        if skill.tools:
            for tool_name in skill.tools:
                if tool_name in TOOL_DEFINITIONS:
                    tools.append(TOOL_DEFINITIONS[tool_name])
                else:
                    self.journal.print(f"⚠️ Unknown tool '{tool_name}' in skill '{skill.name}'")

        session = ChatSession(
            client=self.clients[provider],
            provider_name=provider,
            model=model,
            journal=self.journal,
            cost_callback=self._track_cost,
            system_prompt=system_prompt,
            temperature=skill.temperature,
            max_tokens=skill.max_tokens,
            log_action=skill.name,
            log_title=log_title,
            response_schema=skill.response_schema,
            response_format=skill.response_format,
            tools=tools,
        )

        if skill.user_content:
            user_content = skill.user_content.format(**kwargs)
            session.messages.append({"role": "user", "content": user_content})

        return session

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
