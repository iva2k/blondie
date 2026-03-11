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


def test_check_run_limit_within_limit(router):
    """Test check passes when cost is low."""
    router.daily_cost = 5.0
    is_within_limit, reason = router.check_run_limit()
    assert is_within_limit is True
    assert reason == "WITHIN_LIMIT"


def test_check_run_limit_exceeded(router):
    """Test check fails when cost is high."""
    router.daily_cost = 15.0
    is_within_limit, reason = router.check_run_limit()
    assert is_within_limit is False
    assert reason == "DAILY_LIMIT_EXCEEDED"


def test_check_run_limit_reset(router):
    """Test cost resets on a new day."""
    # Set last reset to yesterday
    yesterday = datetime.date.today() - datetime.timedelta(days=1)
    router.last_reset_date = yesterday
    router.daily_cost = 15.0  # Over limit

    # Should reset and pass
    is_within_limit, reason = router.check_run_limit()
    assert is_within_limit is True
    assert reason == "WITHIN_LIMIT"
    assert router.daily_cost == pytest.approx(0.0)
    assert router.last_reset_date == datetime.date.today()


def test_check_total_limit_exceeded(router):
    """Test check fails when total cost is high."""
    router.policy.limits = {"max_total_cost_usd": 100.0, "max_daily_cost_usd": 50.0}
    router.total_cost = 101.0
    router.daily_cost = 10.0

    is_within_limit, reason = router.check_run_limit()
    assert is_within_limit is False
    assert reason == "TOTAL_LIMIT_EXCEEDED"


def test_usage_persistence(router):
    """Test usage persistence."""
    # Since config path is in tmp_path, usage.yaml is also in tmp_path
    assert router.usage_path.parent.exists()

    # Simulate tracking cost
    # pylint: disable=protected-access
    router._track_cost(1.5)

    assert router.usage_path.exists()
    content = router.usage_path.read_text(encoding="utf-8")
    assert "daily_cost: 1.5" in content
    assert "total_cost: 1.5" in content

    # Modify usage file to test loading
    today = datetime.date.today()
    router.usage_path.write_text(f"daily_cost: 5.0\ntotal_cost: 10.0\ndate: {today.isoformat()}", encoding="utf-8")

    # Reset internal state to ensure load actually changes it
    router.daily_cost = 0.0
    router.total_cost = 0.0

    # Reload
    router._load_usage()

    assert router.daily_cost == pytest.approx(5.0)
    assert router.total_cost == pytest.approx(10.0)
    assert router.last_reset_date == today
