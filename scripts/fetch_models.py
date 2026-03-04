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


# Known costs per 1M tokens (Input / Output)
# As of late 2024 / early 2025
KNOWN_COSTS = {
    "openai": {
        "gpt-4o": {"input": 2.50, "output": 10.00},
        "gpt-4o-2024-05-13": {"input": 5.00, "output": 15.00},
        "gpt-4o-2024-08-06": {"input": 2.50, "output": 10.00},
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "gpt-4-turbo": {"input": 10.00, "output": 30.00},
        "gpt-4-turbo-preview": {"input": 10.00, "output": 30.00},
        "gpt-4": {"input": 30.00, "output": 60.00},
        "gpt-3.5-turbo-0125": {"input": 0.50, "output": 1.50},
        "o1-preview": {"input": 15.00, "output": 60.00},
        "o1-mini": {"input": 3.00, "output": 12.00},
    },
    "anthropic": {
        "claude-3-5-sonnet-20240620": {"input": 3.00, "output": 15.00},
        "claude-3-opus-20240229": {"input": 15.00, "output": 75.00},
        "claude-3-sonnet-20240229": {"input": 3.00, "output": 15.00},
        "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
    },
}

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

    # Load existing data to preserve costs
    existing_data = {}
    if output_path.exists():

        def load_existing() -> dict:
            with open(output_path, encoding="utf-8") as f:
                return yaml.safe_load(f) or {}

        existing_data = await asyncio.to_thread(load_existing)

    # Prepare output structure
    output_data = existing_data.copy()

    for name, client_cls in LLM_CLIENTS.items():
        title, name = name, name.lower().replace(" ", "_")

        # Ensure structure exists
        if name not in output_data:
            output_data[name] = {}
        if isinstance(output_data[name], list):
            output_data[name] = {"models": output_data[name]}

        # Update costs
        if name in KNOWN_COSTS:
            if "costs" not in output_data[name]:
                output_data[name]["costs"] = {}
            
            output_data[name]["costs"].update(KNOWN_COSTS[name])
            print(f"  💰 Updated costs for {title}")

        # Fetch models
        if name not in llm_secrets:
            continue
        secret = llm_secrets.get(name)
        if not secret or not secret.get("api_key"):
            continue
        print(f"Fetching {title} models...")
        client = client_cls(
            api_key=secret["api_key"],
            base_url=secret.get("api_base", ""),
            model="dummy",
        )
        try:
            models = await client.list_models()

            # Update models list
            output_data[name]["models"] = sorted(models)

            print(f"  ✅ Found {len(models)} models")
        except Exception as e:  # pylint: disable=broad-exception-caught
            print(f"  ❌ Failed: {e}")
        finally:
            await client.close()

    if output_data:

        def save_models() -> None:
            with open(output_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(output_data, f)

        await asyncio.to_thread(save_models)
        print(f"💾 Saved models to {output_path}")
    else:
        print("⚠️  No models fetched.")


if __name__ == "__main__":
    asyncio.run(main())
