# tests/agent/test_router_daily_limit.py

"""Unit tests for LLMRouter daily limit logic."""

import datetime
from unittest.mock import MagicMock, patch

import pytest

from agent.router import LLMRouter


@pytest.fixture
def router(tmp_path):
    """Create a router with mocked config."""
    secrets = tmp_path / "secrets.yaml"
    secrets.write_text("llm: {}", encoding="utf-8")
    config = tmp_path / "config.yaml"
    config.write_text("providers: {}", encoding="utf-8")

    with (
        patch("agent.router.LLMRouter._load_secrets", return_value={}),
        patch("agent.router.LLMRouter._load_known_models", return_value=({}, {})),
        patch("agent.router.LLMRouter._init_clients"),
    ):
        r = LLMRouter(secrets, config)
        r.policy = MagicMock()
        r.policy.limits = {"max_daily_cost_usd": 10.0}
        return r


def test_check_daily_limit_within_limit(router):
    """Test check passes when cost is low."""
    router.daily_cost = 5.0
    assert router.check_daily_limit() is True


def test_check_daily_limit_exceeded(router):
    """Test check fails when cost is high."""
    router.daily_cost = 15.0
    assert router.check_daily_limit() is False


def test_check_daily_limit_reset(router):
    """Test cost resets on a new day."""
    # Set last reset to yesterday
    yesterday = datetime.date.today() - datetime.timedelta(days=1)
    router.last_reset_date = yesterday
    router.daily_cost = 15.0  # Over limit

    # Should reset and pass
    assert router.check_daily_limit() is True
    assert router.daily_cost == 0.0
    assert router.last_reset_date == datetime.date.today()
