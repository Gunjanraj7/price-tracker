"""Seeing prices now, and tracking products: add, list, check, target, remove."""

import argparse

import httpx
from sqlalchemy.orm import Session

from .. import db, notify, tracking
from ..errors import FetchError, NotifyError, TrackingError
from ..fetch import fetch_product, new_client
from ..prices import format_rupees
from .output import price_text, print_alerts, short, target_text, when


def run(args: argparse.Namespace) -> int:
    """add, list, check, target or remove. `add` and `check` send new alerts to Telegram after."""
    with db.connect() as session:
        try:
            if args.command == "list":
                return list_items(session)
            if args.command == "target":
                tracking.set_target(session, args.item, args.price)
                print(f"Item {args.item} target: {format_rupees(args.price) if args.price is not None else 'none'}")
                return 0
            if args.command == "remove":
                tracking.untrack(session, args.item)
                print(f"Stopped tracking item {args.item}.")
                return 0
        except TrackingError as error:
            print(f"Error:    {error}")
            return 1

        with new_client() as client:
            code = add(session, client, args) if args.command == "add" else check(session, client)
        if not send_alerts(session):
            code = 1
        return code


def show_links(links: list[str]) -> int:
    """Print the price of each link, or of each link pasted, without saving anything."""
    with new_client() as client:
        if links:
            results = []
            for number, link in enumerate(links):
                if number:
                    print()
                results.append(show(link, client))     # the fetcher pauses between store requests
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


def add(session: Session, client: httpx.Client, args: argparse.Namespace) -> int:
    try:
        result = tracking.track(session, args.link, client, target=args.target, name=args.name, item_id=args.to)
    except (FetchError, TrackingError) as error:
        print(f"Error:    {error}")
        return 1

    listing = result.listing
    item = listing.item
    print(f"{'Added to' if args.to else 'Tracking as'} item {item.id}: {short(item.name)}")
    print(f"Store:    {listing.site}")
    print(f"Price:    {price_text(listing)}")
    print(f"Target:   {target_text(item)}")
    print_alerts(result.alerts)
    return 0


def list_items(session: Session) -> int:
    items = db.all_items(session)
    if not items:
        print('Nothing tracked yet. Start with: python -m price_tracker add "<link>"')
        return 0

    for number, item in enumerate(items):
        if number:
            print()
        paused = "" if item.active else "  (paused)"
        print(f"Item {item.id}: {short(item.name)}{paused}")
        print(f"    target    {target_text(item)}")
        for listing in item.listings:
            print(f"    {listing.site:<9} {price_text(listing):<14} checked {when(listing.last_checked_at)}")
            if listing.last_error:
                print(f"              last check failed: {listing.last_error}")
    return 0


def check(session: Session, client: httpx.Client) -> int:
    count = len(db.listings_to_check(session))
    if not count:
        print('Nothing to check. Start with: python -m price_tracker add "<link>"')
        return 0

    names = {item.id: short(item.name, 40) for item in db.all_items(session)}
    print(f"Checking {count} store page{'s' if count > 1 else ''}...")
    alerts, failed = [], False
    for result in tracking.check_all(session, client):
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


def send_alerts(session: Session) -> bool:
    """Send the alerts not sent yet to Telegram, if it's set up. Returns False if sending failed."""
    telegram = notify.from_environment()
    if telegram is None:
        return True
    with telegram:
        try:
            sent = notify.send_alerts(session, telegram)
        except NotifyError as error:
            print(f"Telegram: couldn't send alerts. {error}")
            return False
    if sent:
        print(f"Telegram: sent {sent} alert{'s' if sent > 1 else ''}.")
    return True
