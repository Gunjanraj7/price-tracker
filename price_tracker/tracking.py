"""Tracking products: saving them, checking their prices and making alerts.

    from price_tracker import db, new_client, tracking

    conn = db.connect()
    with new_client() as client:
        tracking.track(conn, "https://www.amazon.in/dp/B088FKCD4J", client, target=Decimal("1500"))
        for check in tracking.check_all(conn, client):
            print(check.listing.site, check.product.price if check.product else check.error)
"""

import sqlite3
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from textwrap import shorten

import httpx

from . import config, db
from .alerts import find_alerts
from .errors import FetchError, TrackingError
from .fetch import fetch_product
from .models import Listing, ProductInfo
from .prices import format_rupees


@dataclass
class Check:
    """The result of checking one listing."""

    listing: Listing
    product: ProductInfo | None = None              # None when the check failed
    error: str | None = None                        # why it failed
    alerts: list[str] = field(default_factory=list)  # messages of the alerts it made


def track(
    conn: sqlite3.Connection,
    link: str,
    client: httpx.Client,
    target: Decimal | None = None,
    name: str | None = None,
    item_id: int | None = None,
    now: datetime | None = None,
) -> Check:
    """Start tracking the product at `link`, and save its current price.

    This makes a new item, called `name` (the store's title by default).
    Give `item_id` to add the link to an item you already track instead, like
    the Flipkart page of a product you track on Amazon. `target` sets the
    item's target price. Raises TrackingError if the item doesn't exist or
    the product is already tracked, and FetchError if the page can't be read.
    """
    if item_id is not None and db.get_item(conn, item_id) is None:
        raise TrackingError(f"There is no item {item_id}.")

    product = fetch_product(link, client)
    existing = db.find_listing(conn, product.site, product.product_id)
    if existing:
        raise TrackingError(f"This product is already tracked, as item {existing.item_id}.")

    now = now or db.utc_now()
    with conn:
        if item_id is None:
            item_id = db.add_item(conn, name or product.title or product.product_id, target, now)
        elif target is not None:
            db.set_target(conn, item_id, target)
        listing = db.get_listing(conn, db.add_listing(conn, item_id, product, now))
        return _save(conn, listing, product, now)


def check(conn: sqlite3.Connection, listing: Listing, client: httpx.Client, now: datetime | None = None) -> Check:
    """Fetch one listing's price now and save it, with any alerts it deserves."""
    now = now or db.utc_now()
    try:
        product = fetch_product(listing.url, client)
    except FetchError as error:
        with conn:
            db.record_error(conn, listing.id, str(error), now)
        return Check(listing, error=str(error))

    with conn:
        return _save(conn, listing, product, now)


def check_all(conn: sqlite3.Connection, client: httpx.Client, now: datetime | None = None) -> Iterator[Check]:
    """Check every listing of the active items, saving each result as it comes in."""
    for number, listing in enumerate(db.listings_to_check(conn)):
        if number:
            time.sleep(config.PAUSE_BETWEEN_PRODUCTS)
        yield check(conn, listing, client, now)


def set_target(conn: sqlite3.Connection, item_id: int, target: Decimal | None) -> None:
    """Change an item's target price; None removes it."""
    if db.get_item(conn, item_id) is None:
        raise TrackingError(f"There is no item {item_id}.")
    with conn:
        db.set_target(conn, item_id, target)


def untrack(conn: sqlite3.Connection, item_id: int) -> None:
    """Stop tracking an item, and delete its price history and alerts."""
    if db.get_item(conn, item_id) is None:
        raise TrackingError(f"There is no item {item_id}.")
    with conn:
        db.delete_item(conn, item_id)


def _save(conn: sqlite3.Connection, listing: Listing, product: ProductInfo, now: datetime) -> Check:
    """Save a fetched price and make the alerts it deserves. Run it inside `with conn:`."""
    earlier = db.prices_since(conn, listing.id, now - timedelta(days=config.BIG_DROP_DAYS))
    db.record_price(conn, listing.id, product, now)

    result = Check(listing, product)
    if not product.in_stock or product.price is None:
        return result

    item = db.get_item(conn, listing.item_id)
    repeat_window = now - timedelta(days=config.ALERT_REPEAT_DAYS)
    for alert in find_alerts(product.price, item.target_price, earlier):
        sent = db.alert_prices_since(conn, listing.id, alert.kind, repeat_window)
        if any(price <= alert.price for price in sent):
            continue
        name = shorten(item.name, 60, placeholder="…")
        message = f"{name} is {format_rupees(alert.price)} on {listing.site.capitalize()}, {alert.reason}"
        db.add_alert(conn, listing.id, alert.kind, alert.price, message, now)
        result.alerts.append(message)
    return result
