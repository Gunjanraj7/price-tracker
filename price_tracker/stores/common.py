"""Page-reading helpers shared by the store parsers."""

import json

from bs4 import BeautifulSoup, Tag

from ..errors import Blocked
from ..prices import parse_price

# Signs of a "prove you are human" page instead of a product page.
BLOCK_MARKERS = (
    "validateCaptcha",                      # Amazon's "type the characters" form
    "Enter the characters you see below",
    "triggerInterstitialChallenge",         # JavaScript "checking your browser" page
    "bm-verify",
)


def check_not_blocked(html: str) -> None:
    if any(marker in html for marker in BLOCK_MARKERS):
        raise Blocked("The store showed a CAPTCHA or browser check instead of the product.")


def select_text(soup: Tag, selector: str) -> str | None:
    """The text of the first element matching `selector`, or None."""
    tag = soup.select_one(selector)
    return tag.get_text(" ", strip=True) if tag else None


def from_json_ld(soup: BeautifulSoup) -> dict | None:
    """Read the standard product data many stores embed for search engines.

    Looks for <script type="application/ld+json"> with a schema.org Product.
    Returns {"title", "price", "currency", "in_stock"} or None.
    """
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except json.JSONDecodeError:
            continue

        # The block can be one object, a list, or {"@graph": [...]}.
        if isinstance(data, dict):
            items = data.get("@graph", [data])
        elif isinstance(data, list):
            items = data
        else:
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            types = item.get("@type")
            if types != "Product" and not (isinstance(types, list) and "Product" in types):
                continue

            offers = item.get("offers") or {}
            if isinstance(offers, list):
                offers = offers[0] if offers else {}
            price = parse_price(str(offers.get("price") or offers.get("lowPrice") or ""))
            availability = str(offers.get("availability", "InStock"))
            return {
                "title": item.get("name"),
                "price": price,
                "currency": offers.get("priceCurrency", "INR"),
                "in_stock": "OutOfStock" not in availability and "SoldOut" not in availability,
            }
    return None
