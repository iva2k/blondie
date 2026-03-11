# tests/lib/test_webscrape.py

"""Unit tests for webscrape module."""

from unittest.mock import AsyncMock, patch

import pytest

from lib.webscrape import (
    _parse_price,
    extract_structured_data,
    fetch_page_content,
    parse_pricing_from_data,
    scrape_pricing,
)


@pytest.mark.parametrize(
    "text, expected",
    [
        ("$2.50 / 1M tokens", 2.50),
        ("Free", 0.0),
        ("$1,000.00 / 1M tokens", 1000.00),
        ("$0.50 / 1K tokens", 500.0),
        ("No price here", 0.0),
    ],
)
def test_parse_price(text, expected):
    """Test price string parsing."""
    assert _parse_price(text) == pytest.approx(expected)


def test_extract_structured_data_table():
    """Test extracting data from a standard HTML table."""
    html = """
    <table>
      <thead><tr><th>Model</th><th>Input</th><th>Output</th></tr></thead>
      <tbody>
        <tr><td>gpt-4</td><td>$10.00</td><td>$30.00</td></tr>
        <tr><td>gpt-3.5</td><td>$0.50</td><td>$1.50</td></tr>
      </tbody>
    </table>
    """
    data = extract_structured_data(html, "table")
    assert len(data) == 1
    assert len(data[0]) == 2
    assert data[0][0]["Model"] == "gpt-4"
    assert data[0][1]["Input"] == "$0.50"


def test_extract_structured_data_cards():
    """Test extracting data from div-based cards."""
    html = """
    <div class="card">
      <h3>claude-3-opus</h3>
      <div class="label">Input</div><div>$15.00</div>
      <div class="label">Output</div><div>$75.00</div>
    </div>
    <div class="card">
      <h3>claude-3-sonnet</h3>
      <div class="label">Input</div><div>$3.00</div>
      <div class="label">Output</div><div>$15.00</div>
    </div>
    """
    data = extract_structured_data(html, ".card")
    assert len(data) == 1
    assert len(data[0]) == 2
    assert data[0][0]["Model"] == "claude-3-opus"
    assert data[0][1]["Input"] == "$3.00"


def test_parse_pricing_from_data():
    """Test parsing pricing from structured data."""
    structured_data = [
        [
            {"Model": "gpt-4o", "Input / 1M tokens": "$5.00", "Output / 1M tokens": "$15.00"},
            {"Model": "gpt-4-turbo", "Input / 1M tokens": "$10.00", "Output / 1M tokens": "$30.00"},
        ]
    ]
    hint = {"model": "Model", "input": "Input", "output": "Output"}
    costs = parse_pricing_from_data(structured_data, hint)

    assert "gpt-4o" in costs
    assert costs["gpt-4o"]["input"] == pytest.approx(5.0)
    assert costs["gpt-4-turbo"]["output"] == pytest.approx(30.0)


@pytest.mark.asyncio
async def test_scrape_pricing_e2e():
    """Test the full scrape_pricing flow with mocks."""
    html = "<table><tr><th>Model</th><th>Input</th></tr><tr><td>gpt-4</td><td>$10</td></tr></table>"
    hint = '{"model": "Model", "input": "Input"}'

    with patch("lib.webscrape.fetch_page_content", new_callable=AsyncMock, return_value=html) as mock_fetch:
        costs = await scrape_pricing("provider", "http://test.com", "table", hint)

        mock_fetch.assert_called_with("http://test.com")
        assert "gpt-4" in costs
        assert costs["gpt-4"]["input"] == pytest.approx(10.0)
        assert costs["gpt-4"]["output"] == pytest.approx(0.0)


@pytest.mark.asyncio
async def test_fetch_page_content_playwright_failure():
    """Test that fetch_page_content handles playwright errors gracefully."""
    with patch("lib.webscrape.async_playwright") as mock_playwright:
        mock_playwright.return_value.__aenter__.side_effect = Exception("Playwright failed")
        content = await fetch_page_content("http://test.com")
        assert content == ""
