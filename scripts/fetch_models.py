# scripts/fetch_models.py

"""Fetch available LLM models and save to .agent/llm.yaml."""

import asyncio
import sys
from pathlib import Path

import yaml

# Add src to path to allow imports
sys.path.append(str(Path(__file__).parents[1] / "src"))

# pylint: disable=wrong-import-position
from llm.client import LLM_CLIENTS


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

    for name, client_cls in LLM_CLIENTS.items():
        title, name = name, name.lower().replace(" ", "_")
        if name not in llm_secrets:
            continue
        secret = llm_secrets.get(name)
        if not secret.get("api_key"):
            continue
        print(f"Fetching {title} models...")
        client = client_cls(
            api_key=secret["api_key"],
            base_url=secret.get("api_base", ""),
            model="dummy",
        )
        try:
            models = await client.list_models()
            models_data[name] = sorted(models)
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
