"""Command line: see prices now, or track products and get alerts.

Usage, from the project folder:
    python -m price_tracker                          asks you to paste links, one at a time
    python -m price_tracker "<link>" ["<link>" ...]  shows their prices now, without saving them

    python -m price_tracker add "<link>" [--target PRICE] [--name NAME]
                                                     starts tracking a product
    python -m price_tracker add "<link>" --to ITEM   adds another store's page to item ITEM
    python -m price_tracker list                     shows tracked items and their latest prices
    python -m price_tracker check                    checks every tracked item now and shows alerts
    python -m price_tracker target ITEM PRICE        changes an item's target price ("off" removes it)
    python -m price_tracker remove ITEM              stops tracking an item and deletes its history

Tracked items are saved in price_tracker.db, in the project folder.

A link can be a normal product link, a short share link (amzn.in/d/...,
dl.flipkart.com/s/...) or the whole message the store app shares.
In PowerShell or cmd, put links in quotes: they often contain '&'.
"""

import argparse
import re
import sqlite3
import sys
import time
from contextlib import closing
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from textwrap import shorten

import httpx

from . import config, db, tracking
from .errors import FetchError, TrackingError
from .fetch import fetch_product, new_client
from .models import Item, Listing
from .prices import format_rupees, parse_price

COMMANDS = ("add", "list", "check", "target", "remove", "-h", "--help")

IST = timezone(timedelta(hours=5, minutes=30))


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


def show_links(links: list[str]) -> int:
    """Print the price of each link, or of each link pasted, without saving anything."""
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


def price_arg(text: str) -> Decimal | None:
    """Read a price typed on the command line, like 1500, 1,499.50 or ₹60,000. "off" means none."""
    if text.strip().lower() == "off":
        return None
    cleaned = re.sub(r"^(₹|rs\.?)\s*", "", text.strip(), flags=re.IGNORECASE)
    if not re.fullmatch(r"\d[\d,]*(\.\d{1,2})?", cleaned):
        raise argparse.ArgumentTypeError(f"{text!r} is not a price; write it like 1500 or 1,499.50")
    price = parse_price(cleaned)
    if not price:
        raise argparse.ArgumentTypeError("the price must be more than ₹0")
    return price


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m price_tracker",
        description='Track Amazon.in and Flipkart prices. Give links without a command to just see their prices.',
    )
    commands = parser.add_subparsers(dest="command", required=True)

    add = commands.add_parser("add", help="start tracking a product")
    add.add_argument("link")
    add.add_argument("--target", type=price_arg, help="alert when the price gets close to this, e.g. 1500")
    add.add_argument("--name", help="your own name for it (default: the store's title)")
    add.add_argument("--to", type=int, metavar="ITEM", help="add the link to item ITEM, e.g. its page on the other store")

    commands.add_parser("list", help="show tracked items and their latest prices")
    commands.add_parser("check", help="check every tracked item now and show alerts")

    target = commands.add_parser("target", help="change an item's target price")
    target.add_argument("item", type=int)
    target.add_argument("price", type=price_arg, help='e.g. 1500, or "off" for no target')

    remove = commands.add_parser("remove", help="stop tracking an item and delete its history")
    remove.add_argument("item", type=int)
    return parser


def when(moment: datetime) -> str:
    """Write a time for people, in Indian time: '04 Nov, 11:00 AM'."""
    return moment.astimezone(IST).strftime("%d %b, %I:%M %p")


def short(name: str, width: int = 60) -> str:
    return shorten(name, width, placeholder="…")


def price_text(listing: Listing) -> str:
    if listing.last_in_stock and listing.last_price is not None:
        return format_rupees(listing.last_price)
    return "not available"


def target_text(item: Item) -> str:
    return format_rupees(item.target_price) if item.target_price is not None else "none"


def print_alerts(alerts: list[str]) -> None:
    for message in alerts:
        print(f"Alert:    {message}")


def add(conn: sqlite3.Connection, client: httpx.Client, args: argparse.Namespace) -> int:
    try:
        result = tracking.track(conn, args.link, client, target=args.target, name=args.name, item_id=args.to)
    except (FetchError, TrackingError) as error:
        print(f"Error:    {error}")
        return 1

    item = db.get_item(conn, result.listing.item_id)
    listing = db.get_listing(conn, result.listing.id)
    print(f"{'Added to' if args.to else 'Tracking as'} item {item.id}: {short(item.name)}")
    print(f"Store:    {listing.site}")
    print(f"Price:    {price_text(listing)}")
    print(f"Target:   {target_text(item)}")
    print_alerts(result.alerts)
    return 0


def list_items(conn: sqlite3.Connection) -> int:
    items = db.all_items(conn)
    if not items:
        print('Nothing tracked yet. Start with: python -m price_tracker add "<link>"')
        return 0

    for number, item in enumerate(items):
        if number:
            print()
        paused = "" if item.active else "  (paused)"
        print(f"Item {item.id}: {short(item.name)}{paused}")
        print(f"    target    {target_text(item)}")
        for listing in db.listings_of(conn, item.id):
            print(f"    {listing.site:<9} {price_text(listing):<14} checked {when(listing.last_checked_at)}")
            if listing.last_error:
                print(f"              last check failed: {listing.last_error}")
    return 0


def check(conn: sqlite3.Connection, client: httpx.Client) -> int:
    count = len(db.listings_to_check(conn))
    if not count:
        print('Nothing to check. Start with: python -m price_tracker add "<link>"')
        return 0

    names = {item.id: short(item.name, 40) for item in db.all_items(conn)}
    print(f"Checking {count} store page{'s' if count > 1 else ''}...")
    alerts, failed = [], False
    for result in tracking.check_all(conn, client):
        listing = result.listing
        if result.error:
            state, failed = f"check failed: {result.error}", True
        elif result.product.in_stock and result.product.price is not None:
            state = format_rupees(result.product.price)
        else:
            state = "not available"
        print(f"#{listing.item_id:<3} {names[listing.item_id]:<40}  {listing.site:<9} {state}")
        alerts += result.alerts

    print()
    if alerts:
        print_alerts(alerts)
    else:
        print("No alerts.")
    return 1 if failed else 0


def run(args: argparse.Namespace) -> int:
    with closing(db.connect()) as conn:
        try:
            if args.command == "list":
                return list_items(conn)
            if args.command == "target":
                tracking.set_target(conn, args.item, args.price)
                print(f"Item {args.item} target: {format_rupees(args.price) if args.price is not None else 'none'}")
                return 0
            if args.command == "remove":
                tracking.untrack(conn, args.item)
                print(f"Stopped tracking item {args.item}.")
                return 0
        except TrackingError as error:
            print(f"Error:    {error}")
            return 1

        with new_client() as client:
            if args.command == "add":
                return add(conn, client, args)
            return check(conn, client)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    # Windows terminals can choke on the ₹ sign without this.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    if args and args[0] in COMMANDS:
        return run(build_parser().parse_args(args))
    return show_links(args)
