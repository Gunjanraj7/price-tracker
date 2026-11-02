"""Command line: print the current price of products from their links.

Usage, from the project folder:
    python -m price_tracker                          asks you to paste links, one at a time
    python -m price_tracker "<link>" ["<link>" ...]  checks the links you give it

A link can be a normal product link, a short share link (amzn.in/d/...,
dl.flipkart.com/s/...) or the whole message the store app shares.
In PowerShell or cmd, put links in quotes: they often contain '&'.
"""

import sys
import time

import httpx

from . import config
from .errors import FetchError
from .fetch import fetch_product, new_client
from .prices import format_rupees


def show(link: str, client: httpx.Client) -> bool:
    """Fetch one product and print it. Returns False if it failed."""
    try:
        product = fetch_product(link, client)
    except FetchError as error:
        print(f"Error:    {error}")
        return False

    print(f"Store:    {product.site}")
    print(f"ID:       {product.product_id}")
    print(f"Title:    {product.title}")
    if product.in_stock:
        print(f"Price:    {format_rupees(product.price)}")
    else:
        print("Price:    not available right now (out of stock or no seller)")
    print(f"Link:     {product.url}")
    return True


def main(argv: list[str] | None = None) -> int:
    links = sys.argv[1:] if argv is None else argv
    # Windows terminals can choke on the ₹ sign without this.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    with new_client() as client:
        if links:
            results = []
            for number, link in enumerate(links):
                if number:
                    print()
                    time.sleep(config.PAUSE_BETWEEN_PRODUCTS)
                results.append(show(link, client))
            return 0 if all(results) else 1

        print("Paste an Amazon.in or Flipkart product link and press Enter.")
        print("Press Enter on an empty line to quit.")
        while True:
            try:
                link = input("\nLink: ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return 0
            if not link:
                return 0
            show(link, client)
