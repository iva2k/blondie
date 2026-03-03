# scripts/fetch_models.py

"""Fetch available LLM models and save to .agent/llm.yaml."""

import asyncio
import sys
from pathlib import Path

import yaml

# Add src to path to allow imports
sys.path.append(str(Path(__file__).parents[1] / "src"))

# pylint: disable=wrong-import-position
from llm.client import AnthropicClient, LLMClient, OpenAIClient


async def main() -> None:
    """Fetch models from configured providers."""
    root_dir = Path(__file__).parents[1]
    agent_dir = root_dir / ".agent"
    secrets_path = agent_dir / "secrets.env.yaml"
    output_path = agent_dir / "llm.yaml"

    if not secrets_path.exists():
        print(f"❌ Secrets file not found: {secrets_path}")
        return

    def load_secrets() -> dict:
        with open(secrets_path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    secrets = await asyncio.to_thread(load_secrets)

    llm_secrets = secrets.get("llm", {})
    models_data: dict[str, list[str]] = {}

    client: LLMClient | None = None

    # OpenAI
    openai_secret = llm_secrets.get("openai")
    if openai_secret and openai_secret.get("api_key"):
        print("Fetching OpenAI models...")
        client = OpenAIClient(
            api_key=openai_secret["api_key"],
            base_url=openai_secret.get("api_base") or "https://api.openai.com/v1",
            model="gpt-4o-mini",  # Dummy model for init
        )
        try:
            models = await client.list_models()
            models_data["openai"] = sorted(models)
            print(f"  ✅ Found {len(models)} models")
        except Exception as e:  # pylint: disable=broad-exception-caught
            print(f"  ❌ Failed: {e}")
        finally:
            await client.close()

    # Anthropic
    anthropic_secret = llm_secrets.get("anthropic")
    if anthropic_secret and anthropic_secret.get("api_key"):
        print("Fetching Anthropic models...")
        client = AnthropicClient(
            api_key=anthropic_secret["api_key"],
            base_url=anthropic_secret.get("api_base") or "https://api.anthropic.com/v1",
            model="claude-3-5-sonnet-20240620",  # Dummy model for init
        )
        try:
            models = await client.list_models()
            models_data["anthropic"] = sorted(models)
            print(f"  ✅ Found {len(models)} models")
        except Exception as e:  # pylint: disable=broad-exception-caught
            print(f"  ❌ Failed: {e}")
        finally:
            await client.close()

    if models_data:

        def save_models() -> None:
            with open(output_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(models_data, f)

        await asyncio.to_thread(save_models)
        print(f"💾 Saved models to {output_path}")
    else:
        print("⚠️  No models fetched.")


if __name__ == "__main__":
    asyncio.run(main())
