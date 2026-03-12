"""Tests for model fetching logic."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml

from agent.lib.models import fetch_and_save_models


@pytest.mark.asyncio
async def test_fetch_and_save_models_success(tmp_path):
    """Test successful model fetching and saving."""
    secrets = {"llm": {"mock_provider": {"api_key": "sk-test"}}}
    output_path = tmp_path / "llm.yaml"

    # Mock LLM Client
    mock_client_cls = MagicMock()
    mock_client_instance = AsyncMock()
    mock_client_cls.return_value = mock_client_instance
    mock_client_instance.list_models.return_value = ["model-a", "model-b"]
    mock_client_instance.close = AsyncMock()

    # Configure client class attributes for pricing
    mock_client_cls.pricing_url = "http://pricing"
    mock_client_cls.pricing_selector = "sel"
    mock_client_cls.pricing_hint = "hint"

    # Mock pricing scrape
    mock_pricing = {"model-a": {"input": 1.0}}

    with (
        patch.dict("agent.lib.models.LLM_CLIENTS", {"Mock Provider": mock_client_cls}, clear=True),
        patch("agent.lib.models.scrape_pricing", new_callable=AsyncMock) as mock_scrape,
    ):
        mock_scrape.return_value = mock_pricing

        # Execute
        result = await fetch_and_save_models(secrets, output_path, log_func=MagicMock())

        assert result is True
        assert output_path.exists()

        data = yaml.safe_load(output_path.read_text(encoding="utf-8"))

        assert "mock_provider" in data
        assert data["mock_provider"]["models"] == ["model-a", "model-b"]
        assert data["mock_provider"]["costs"] == mock_pricing
        assert "last_updated" in data["mock_provider"]


@pytest.mark.asyncio
async def test_fetch_and_save_models_partial_failure(tmp_path):
    """Test handling of client errors and preserving existing data."""
    output_path = tmp_path / "llm.yaml"

    # Create existing data
    existing_data = {"existing_provider": {"models": ["old-model"]}}
    output_path.write_text(yaml.safe_dump(existing_data), encoding="utf-8")

    secrets = {"llm": {"fail_provider": {"api_key": "sk-fail"}}}

    # Mock Client that raises exception
    mock_client_cls = MagicMock()
    mock_client_instance = AsyncMock()
    mock_client_cls.return_value = mock_client_instance
    mock_client_instance.list_models.side_effect = Exception("API Error")
    mock_client_instance.close = AsyncMock()
    mock_client_cls.pricing_url = None

    with patch.dict("agent.lib.models.LLM_CLIENTS", {"Fail Provider": mock_client_cls}, clear=True):
        # Execute
        log_mock = MagicMock()
        result = await fetch_and_save_models(secrets, output_path, log_func=log_mock)

        # Should return True because we preserved existing data, even if fetch failed?
        # Actually implementation returns True if success OR output_data is not empty.
        assert result is True

        data = yaml.safe_load(output_path.read_text(encoding="utf-8"))

        # Existing data preserved
        assert "existing_provider" in data
        # Failed provider structure NOT initialized if failure occurred and no costs found
        assert "fail_provider" not in data

        # Check logs
        log_calls = [str(c) for c in log_mock.call_args_list]
        assert any("check failed: API Error" in c for c in log_calls)


@pytest.mark.asyncio
async def test_fetch_models_no_secrets(tmp_path):
    """Test behavior when no secrets are provided."""
    output_path = tmp_path / "llm.yaml"
    secrets = {}

    mock_client_cls = MagicMock()
    mock_client_cls.pricing_url = ""
    with patch.dict("agent.lib.models.LLM_CLIENTS", {"Provider": mock_client_cls}, clear=True):
        result = await fetch_and_save_models(secrets, output_path)

    assert result is False
    assert not output_path.exists()
