# src/llm/client.py

"""LLM HTTP clients for Blondie."""

from dataclasses import dataclass
from typing import Any

import httpx
from rich.console import Console

console = Console()


@dataclass
class LLMResponse:
    """LLM Response dataclass."""

    content: str
    model: str
    tokens_used: int
    cost_usd: float = 0.0


class LLMClient:
    """Abstract base HTTP LLM client."""

    def __init__(self, api_key: str, base_url: str, model: str):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(120.0))

    async def chat(self, messages: list[dict[str, str]], **kwargs: Any) -> LLMResponse:
        """Send chat completion request."""
        raise NotImplementedError

    async def close(self) -> None:
        """Cleanup HTTP client."""
        await self.client.aclose()


class OpenAIClient(LLMClient):
    """OpenAI / OpenAI-compatible (GPT, Ollama, vLLM, etc.)."""

    async def chat(self, messages: list[dict[str, str]], **kwargs: Any) -> LLMResponse:
        payload = {
            "model": kwargs.get("model") or self.model,
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.1),
            "max_tokens": kwargs.get("max_tokens", 4096),
            "stream": False,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        resp = await self.client.post(
            f"{self.base_url}/chat/completions", json=payload, headers=headers
        )
        resp.raise_for_status()
        data = resp.json()

        choice = data["choices"][0]["message"]
        usage = data["usage"]

        return LLMResponse(
            content=choice["content"],
            model=self.model,
            tokens_used=usage["total_tokens"],
            cost_usd=usage["total_tokens"] * 0.00002,  # GPT-4o-mini pricing
        )


class AnthropicClient(LLMClient):
    """Anthropic Claude API."""

    async def chat(self, messages: list[dict[str, str]], **kwargs: Any) -> LLMResponse:
        # Flatten OpenAI messages to Anthropic format
        system = ""
        user_content = ""

        for msg in messages:
            if msg["role"] == "system":
                system += msg["content"] + "\n"
            elif msg["role"] == "user":
                user_content += msg["content"] + "\n"

        payload = {
            "model": kwargs.get("model") or self.model,
            "max_tokens": kwargs.get("max_tokens", 4096),
            "messages": [{"role": "user", "content": user_content}],
            "system": system.strip(),
            "temperature": kwargs.get("temperature", 0.1),
        }

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

        resp = await self.client.post(f"{self.base_url}/messages", json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()

        content = data["content"][0]["text"]
        tokens = data.get("usage", {}).get("output_tokens", 0)

        return LLMResponse(
            content=content,
            model=self.model,
            tokens_used=tokens,
            cost_usd=tokens * 0.000075,  # Claude 3.5 Sonnet pricing
        )
