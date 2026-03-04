# src/llm/client.py

"""LLM HTTP clients for Blondie."""

import json
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass
class LLMResponse:
    """LLM Response dataclass."""

    content: str
    model: str
    tokens_used: int
    cost_usd: float = 0.0
    parsed: Any | None = None
    tool_calls: list[dict[str, Any]] | None = None


class LLMClient:
    """Abstract base HTTP LLM client."""

    base_url_default: str = ""
    pricing_url: str = ""
    pricing_selector: str = ""
    pricing_hint: str = ""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        pricing: dict[str, dict[str, float]] | None = None,
    ):
        self.api_key = api_key
        self.base_url = (base_url or self.base_url_default).rstrip("/")
        self.model = model
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(120.0))
        self.pricing = pricing or {}

    async def chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> LLMResponse:
        """Send chat completion request."""
        raise NotImplementedError

    async def list_models(self) -> list[str]:
        """List available models."""
        raise NotImplementedError

    async def close(self) -> None:
        """Cleanup HTTP client."""
        await self.client.aclose()


class OpenAIClient(LLMClient):
    """OpenAI / OpenAI-compatible (GPT, Ollama, vLLM, etc.)."""

    base_url_default: str = "https://api.openai.com/v1"
    pricing_url: str = "https://developers.openai.com/api/docs/pricing?latest-pricing=standard"
    pricing_selector: str = (
        "#content-switcher-latest-pricing > div.content-switcher-panes.astro-cr4aci74 > div:nth-child(3) > table"
    )
    pricing_hint: str = '{"model": "Model", "input": "Input", "output": "Output"}'

    async def chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> LLMResponse:
        payload = {
            "model": kwargs.get("model") or self.model,
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.1),
            "max_tokens": kwargs.get("max_tokens", 4096),
            "stream": False,
        }

        if kwargs.get("tools"):
            payload["tools"] = [{"type": "function", "function": t} for t in kwargs["tools"]]

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        resp = await self.client.post(f"{self.base_url}/chat/completions", json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()

        choice = data["choices"][0]["message"]
        usage = data["usage"]

        # Calculate cost
        cost = 0.0
        if self.model in self.pricing:
            p = self.pricing[self.model]
            input_cost = (usage.get("prompt_tokens", 0) / 1_000_000) * p.get("input", 0.0)
            output_cost = (usage.get("completion_tokens", 0) / 1_000_000) * p.get("output", 0.0)
            cost = input_cost + output_cost

        return LLMResponse(
            content=choice["content"] or "",
            model=self.model,
            tokens_used=usage["total_tokens"],
            cost_usd=cost,
            tool_calls=choice.get("tool_calls"),
        )

    async def list_models(self) -> list[str]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        resp = await self.client.get(f"{self.base_url}/models", headers=headers)
        resp.raise_for_status()
        data = resp.json()
        return [m["id"] for m in data["data"]]


class AnthropicClient(LLMClient):
    """Anthropic Claude API."""

    base_url_default: str = "https://api.anthropic.com/v1"
    # Simple page, some models, cards layout of data:
    # pricing_url: str = "https://claude.com/pricing#api"
    # pricing_selector: str = ".card_pricing_api_wrap"
    # pricing_hint: str = '{"model": "Model", "input": "Input", "output": "Output"}'

    # Detailed pricing page:
    pricing_url: str = "https://platform.claude.com/docs/en/about-claude/pricing"
    pricing_selector: str = "article table"  # Selects tables within the main article content
    pricing_hint: str = '{"model": "Model", "input": "Base Input Tokens", "output": "Output Tokens"}'

    async def chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> LLMResponse:
        # Convert OpenAI messages to Anthropic format
        system = ""
        anthropic_messages = []

        for msg in messages:
            if msg["role"] == "system":
                system += msg["content"]
            elif msg["role"] == "tool":
                # Handle tool results (OpenAI 'tool' role -> Anthropic 'tool_result' block)
                # We assume the previous message was the user/assistant flow.
                # Anthropic expects tool results in a user message.
                # If the last message was user, append to it? No, tool results usually follow assistant tool use.
                # For simplicity in this abstraction, we map 'tool' role to a user message with tool_result content.
                # Note: This is a simplification. Robust mapping requires tracking the tool_use_id.
                # In a robust implementation, we'd expect the input 'messages' to already contain the tool_call_id.
                anthropic_messages.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": msg.get("tool_call_id"),
                                "content": msg["content"],
                            }
                        ],
                    }
                )
            else:
                # User or Assistant
                content = msg["content"]
                # If we stored tool_calls in the message (from previous turn), we need to format them for Anthropic
                if msg.get("tool_calls"):
                    blocks = []
                    if content:
                        blocks.append({"type": "text", "text": content})
                    for tool in msg["tool_calls"]:
                        blocks.append(
                            {
                                "type": "tool_use",
                                "id": tool["id"],
                                "name": tool["function"]["name"],
                                "input": json.loads(tool["function"]["arguments"]),
                            }
                        )
                    anthropic_messages.append({"role": msg["role"], "content": blocks})
                else:
                    anthropic_messages.append({"role": msg["role"], "content": content})

        payload = {
            "model": kwargs.get("model") or self.model,
            "max_tokens": kwargs.get("max_tokens", 4096),
            "messages": anthropic_messages,
            "system": system.strip(),
            "temperature": kwargs.get("temperature", 0.1),
        }

        if kwargs.get("tools"):
            payload["tools"] = [
                {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "input_schema": t["parameters"],
                }
                for t in kwargs["tools"]
            ]

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

        resp = await self.client.post(f"{self.base_url}/messages", json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()

        content_text = ""
        tool_calls = []
        for block in data["content"]:
            if block["type"] == "text":
                content_text += block["text"]
            elif block["type"] == "tool_use":
                tool_calls.append(
                    {
                        "id": block["id"],
                        "type": "function",
                        "function": {
                            "name": block["name"],
                            "arguments": json.dumps(block["input"]),
                        },
                    }
                )

        tokens = data.get("usage", {}).get("output_tokens", 0)

        # Calculate cost
        cost = 0.0
        if self.model in self.pricing:
            p = self.pricing[self.model]
            input_tokens = data.get("usage", {}).get("input_tokens", 0)
            input_cost = (input_tokens / 1_000_000) * p.get("input", 0.0)
            output_cost = (tokens / 1_000_000) * p.get("output", 0.0)
            cost = input_cost + output_cost

        return LLMResponse(
            content=content_text,
            model=self.model,
            tokens_used=tokens,
            cost_usd=cost,
            tool_calls=tool_calls or None,
        )

    async def list_models(self) -> list[str]:
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        resp = await self.client.get(f"{self.base_url}/models", headers=headers)
        resp.raise_for_status()
        data = resp.json()
        return [m["id"] for m in data["data"]]


LLM_CLIENTS: dict[str, type[LLMClient]] = {
    "OpenAI": OpenAIClient,
    "Anthropic": AnthropicClient,
    # Add more clients here
}
