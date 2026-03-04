# src/utils/webscrape.py

"""Web scraping utilities for extracting model pricing."""

import json
import re

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

# Known costs per 1M tokens (Input / Output)
# Used as fallback if scraping fails or for models not found on page
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
        "o1-mini": {"input": 1.10, "output": 4.40},
        "gpt-5.2": {"input": 1.75, "output": 14.00},
        "gpt-5.1": {"input": 1.25, "output": 10.00},
        "gpt-5": {"input": 1.25, "output": 10.00},
        "gpt-5-mini": {"input": 0.25, "output": 2.00},
        "gpt-5-nano": {"input": 0.05, "output": 0.40},
        "gpt-5.3-chat-latest": {"input": 1.75, "output": 14.00},
        "gpt-5.2-chat-latest": {"input": 1.75, "output": 14.00},
        "gpt-5.1-chat-latest": {"input": 1.25, "output": 10.00},
        "gpt-5-chat-latest": {"input": 1.25, "output": 10.00},
        "gpt-5.3-codex": {"input": 1.75, "output": 14.00},
        "gpt-5.2-codex": {"input": 1.75, "output": 14.00},
        "gpt-5.1-codex-max": {"input": 1.25, "output": 10.00},
        "gpt-5.1-codex": {"input": 1.25, "output": 10.00},
        "gpt-5-codex": {"input": 1.25, "output": 10.00},
        "gpt-5.2-pro": {"input": 21.00, "output": 168.00},
        "gpt-5-pro": {"input": 15.00, "output": 120.00},
        "gpt-4.1": {"input": 2.00, "output": 8.00},
        "gpt-4.1-mini": {"input": 0.40, "output": 1.60},
        "gpt-4.1-nano": {"input": 0.10, "output": 0.40},
        "gpt-realtime": {"input": 4.00, "output": 16.00},
        "gpt-realtime-1.5": {"input": 4.00, "output": 16.00},
        "gpt-realtime-mini": {"input": 0.60, "output": 2.40},
        "gpt-4o-realtime-preview": {"input": 5.00, "output": 20.00},
        "gpt-4o-mini-realtime-preview": {"input": 0.60, "output": 2.40},
        "gpt-audio": {"input": 2.50, "output": 10.00},
        "gpt-audio-1.5": {"input": 2.50, "output": 10.00},
        "gpt-audio-mini": {"input": 0.60, "output": 2.40},
        "gpt-4o-audio-preview": {"input": 2.50, "output": 10.00},
        "gpt-4o-mini-audio-preview": {"input": 0.15, "output": 0.60},
        "o1": {"input": 15.00, "output": 60.00},
        "o1-pro": {"input": 150.00, "output": 600.00},
        "o3-pro": {"input": 20.00, "output": 80.00},
        "o3": {"input": 2.00, "output": 8.00},
        "o3-deep-research": {"input": 10.00, "output": 40.00},
        "o4-mini": {"input": 1.10, "output": 4.40},
        "o4-mini-deep-research": {"input": 2.00, "output": 8.00},
        "o3-mini": {"input": 1.10, "output": 4.40},
        "gpt-5.1-codex-mini": {"input": 0.25, "output": 2.00},
        "codex-mini-latest": {"input": 1.50, "output": 6.00},
        "gpt-5-search-api": {"input": 1.25, "output": 10.00},
        "gpt-4o-mini-search-preview": {"input": 0.15, "output": 0.60},
        "gpt-4o-search-preview": {"input": 2.50, "output": 10.00},
        "computer-use-preview": {"input": 3.00, "output": 12.00},
        "gpt-image-1.5": {"input": 5.00, "output": 10.00},
        "chatgpt-image-latest": {"input": 5.00, "output": 10.00},
        "gpt-image-1": {"input": 5.00, "output": 0.0},
        "gpt-image-1-mini": {"input": 2.00, "output": 0.0},
    },
    "anthropic": {
        "claude-3-5-sonnet-20240620": {"input": 3.00, "output": 15.00},
        "claude-3-opus-20240229": {"input": 15.00, "output": 75.00},
        "claude-3-sonnet-20240229": {"input": 3.00, "output": 15.00},
        "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
    },
}


def _parse_price(text: str) -> float:
    """Parse price string like '$2.50 / 1M tokens' to float."""
    text = text.lower().replace(",", "")
    match = re.search(r"\$\s*([\d\.]+)", text)
    if not match:
        return 0.0
    val = float(match.group(1))
    # Heuristic: if text explicitly mentions '1k', multiply by 1000 to normalize to 1M
    if "1k" in text:
        val *= 1000
    return val


async def fetch_page_content(url: str) -> str:
    """Layer 1: Fetch page content, bypassing Cloudflare using Playwright."""
    try:
        async with async_playwright() as p:
            # Launch headless=False to mimic real user and bypass some bot checks
            browser = await p.chromium.launch(headless=False)
            try:
                page = await browser.new_page()
                await page.goto(url, wait_until="networkidle", timeout=60000)

                # Cloudflare check
                content = await page.content()
                if "cloudflare" in content.lower():
                    await page.wait_for_timeout(5000)

                return await page.content()
            finally:
                await browser.close()
    except Exception as e:  # pylint: disable=broad-exception-caught
        print(f"  ⚠️ Playwright fetch failed: {e}")
        return ""


def extract_structured_data(html: str, selector: str) -> list[list[dict[str, str]]]:
    """Layer 2: Extract tables from selected block as list of rows (dicts)."""
    if not html or not selector:
        return []

    soup = BeautifulSoup(html, "html.parser")
    tables_data = []

    # Find elements matching selector
    elements = soup.select(selector)

    # If selector targets a wrapper, find tables inside. If selector targets table, use it.
    target_tables = []
    for el in elements:
        if el.name == "table":
            target_tables.append(el)
        else:
            target_tables.extend(el.find_all("table"))

    for table in target_tables:
        headers = []
        # Try to find headers in thead or first tr
        thead = table.find("thead")
        if thead:
            headers = [th.get_text(strip=True) for th in thead.find_all(["th", "td"])]

        if not headers:
            first_row = table.find("tr")
            if first_row:
                headers = [th.get_text(strip=True) for th in first_row.find_all(["th", "td"])]

        if not headers:
            continue

        rows_data = []
        # Iterate rows (skip header row if it was the first row)
        for row in table.find_all("tr"):
            cols = row.find_all(["td", "th"])
            if not cols:
                continue

            # Simple heuristic: if row looks like headers, skip it
            row_text = [c.get_text(strip=True) for c in cols]
            if row_text == headers:
                continue

            row_dict = {}
            for i, col in enumerate(cols):
                if i < len(headers):
                    row_dict[headers[i]] = col.get_text(strip=True)

            if row_dict:
                rows_data.append(row_dict)

        if rows_data:
            tables_data.append(rows_data)

    # Fallback: If no tables found, try to parse elements as cards (e.g. Anthropic)
    if not tables_data and elements:
        rows_data = []
        for el in elements:
            row_dict = {}
            # Heuristic: Find a title (Model name)
            # Look for h3/h4 or div with 'title' in class
            header = el.find(["h3", "h4"])
            if not header:
                header = el.find(class_=lambda c: c and "title" in c)

            if header:
                row_dict["Model"] = header.get_text(strip=True)

            # Heuristic: Find key-value pairs based on 'label' class
            # This matches Anthropic's structure: <div class="...label">Input</div> <div ...>Value</div>
            labels = el.find_all(class_=lambda c: c and "label" in c)
            for label in labels:
                key = label.get_text(strip=True)
                # Value is typically the next sibling
                val_el = label.find_next_sibling()
                if val_el:
                    row_dict[key] = val_el.get_text(strip=True)

            if row_dict:
                rows_data.append(row_dict)

        if rows_data:
            tables_data.append(rows_data)

    return tables_data


def parse_pricing_from_data(tables: list[list[dict[str, str]]], hint: dict[str, str]) -> dict[str, dict[str, float]]:
    """Layer 3: Extract pricing info from structured data using hint."""
    costs: dict[str, dict[str, float]] = {}

    model_col_hint = hint.get("model", "").lower()
    input_col_hint = hint.get("input", "").lower()
    output_col_hint = hint.get("output", "").lower()

    if not model_col_hint:
        return costs

    for table in tables:
        # Check if this table has relevant columns
        if not table:
            continue

        for row in table:
            # Identify keys for this specific row (needed for card layouts where keys vary)
            keys = list(row.keys())
            model_key = next((k for k in keys if model_col_hint in k.lower()), None)

            if not model_key:
                continue

            model_name = row.get(model_key, "")
            # Clean model name
            model_key_clean = model_name.split("(")[0].strip().lower()
            if not model_key_clean:
                continue

            input_price = 0.0
            output_price = 0.0

            # Find Input Key (Hint -> "prompt" fallback)
            input_key = next((k for k in keys if input_col_hint in k.lower()), None)
            if not input_key:
                input_key = next((k for k in keys if "prompt" in k.lower()), None)

            if input_key:
                input_price = _parse_price(row.get(input_key, ""))

            # Find Output Key (Hint -> "completion" fallback)
            output_key = next((k for k in keys if output_col_hint in k.lower()), None)
            if not output_key:
                output_key = next((k for k in keys if "completion" in k.lower()), None)

            if output_key:
                output_price = _parse_price(row.get(output_key, ""))

            if input_price > 0 or output_price > 0:
                costs[model_key_clean] = {"input": input_price, "output": output_price}

    return costs


async def scrape_pricing(
    _provider: str, url: str, selector: str | None = None, parse_hint: str | None = None
) -> dict[str, dict[str, float]]:
    """Scrape pricing from vendor page."""
    # Do not merge KNOWN_COSTS here; they are used as fallback in router.py
    costs: dict[str, dict[str, float]] = {}

    if not url:
        return costs

    # Layer 1: Fetch
    html = await fetch_page_content(url)
    if not html:
        return costs

    # Layer 2: Extract Structure
    # Default selector to table if not provided
    target_selector = selector or "table"
    tables_data = extract_structured_data(html, target_selector)

    # Layer 3: Parse Data
    hint_dict = {}
    if parse_hint:
        try:
            hint_dict = json.loads(parse_hint)
        except json.JSONDecodeError:
            # Fallback for simple hints or if it's not JSON
            pass

    # Default hints if not provided
    if not hint_dict:
        hint_dict = {"model": "model", "input": "input", "output": "output"}

    scraped_costs = parse_pricing_from_data(tables_data, hint_dict)

    # Merge scraped costs
    costs.update(scraped_costs)

    return costs
