"""Price Tracker Web Scraper

Scrapes product names and prices from a webpage using requests + BeautifulSoup,
calculates average/min/max price, and saves results to JSON and/or CSV.
"""

from __future__ import annotations

import csv
import json
import re
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Configuration — adjust these selectors/URL for the site you want to track
# ---------------------------------------------------------------------------
TARGET_URL = "https://example.com/products"  # <-- change me

# CSS selectors for product elements on the page
ITEM_SELECTOR = ".product-item"        # container for one product
NAME_SELECTOR = ".product-title"       # product name inside the container
PRICE_SELECTOR = ".price"              # price inside the container

OUTPUT_DIR = Path("data")
REQUEST_TIMEOUT = 15
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    )
}


@dataclass
class Product:
    name: str
    price: float
    currency: str
    scraped_at: str


def fetch_page(url: str) -> str:
    """Download the HTML of the target page."""
    response = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return response.text


def parse_price(text: str) -> tuple[float, str]:
    """Extract numeric price and currency symbol/code from a price string."""
    match = re.search(r"([^\d]*?)(\d[\d,]*\.?\d*)", text.strip())
    if not match:
        raise ValueError(f"Could not parse price: {text!r}")
    currency = match.group(1).strip() or "?"
    price = float(match.group(2).replace(",", ""))
    return price, currency


def scrape_products(html: str) -> list[Product]:
    """Parse product names and prices from page HTML."""
    soup = BeautifulSoup(html, "html.parser")
    products: list[Product] = []
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    for item in soup.select(ITEM_SELECTOR):
        name_el = item.select_one(NAME_SELECTOR)
        price_el = item.select_one(PRICE_SELECTOR)
        if not name_el or not price_el:
            continue
        try:
            price, currency = parse_price(price_el.get_text(strip=True))
        except ValueError as exc:
            print(f"[skip] {exc}")
            continue
        products.append(
            Product(
                name=name_el.get_text(strip=True),
                price=price,
                currency=currency,
                scraped_at=now,
            )
        )
    return products


def summarize(products: list[Product]) -> dict:
    """Return basic price statistics."""
    if not products:
        return {"count": 0, "average": None, "min": None, "max": None}
    prices = [p.price for p in products]
    cheapest = min(products, key=lambda p: p.price)
    most_expensive = max(products, key=lambda p: p.price)
    return {
        "count": len(products),
        "average": round(sum(prices) / len(prices), 2),
        "min": min(prices),
        "max": max(prices),
        "cheapest_product": cheapest.name,
        "most_expensive_product": most_expensive.name,
    }


def save_json(products: list[Product], stats: dict, path: Path) -> None:
    payload = {"stats": stats, "products": [asdict(p) for p in products]}
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved JSON -> {path}")


def save_csv(products: list[Product], path: Path) -> None:
    if not products:
        print("No products to save to CSV.")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(asdict(products[0]).keys()))
        writer.writeheader()
        writer.writerows(asdict(p) for p in products)
    print(f"Saved CSV  -> {path}")


def main() -> int:
    OUTPUT_DIR.mkdir(exist_ok=True)

    print(f"Fetching {TARGET_URL} ...")
    try:
        html = fetch_page(TARGET_URL)
    except requests.RequestException as exc:
        print(f"Error fetching page: {exc}", file=sys.stderr)
        return 1

    products = scrape_products(html)
    if not products:
        print(
            "No products found. Check ITEM_SELECTOR / NAME_SELECTOR / "
            "PRICE_SELECTOR against the site's HTML."
        )
        return 0

    stats = summarize(products)
    print("\n--- Price summary ---")
    for key, value in stats.items():
        print(f"{key:>26}: {value}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    save_json(products, stats, OUTPUT_DIR / f"prices_{timestamp}.json")
    save_csv(products, OUTPUT_DIR / f"prices_{timestamp}.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
