"""Tracking products: saving them, checking their prices and making alerts.

    from price_tracker import db, new_client, tracking

    with db.connect() as session, new_client() as client:
        tracking.track(session, "https://www.amazon.in/dp/B088FKCD4J", client, target=Decimal("1500"))
        for check in tracking.check_all(session, client):
            print(check.listing.site, check.product.price if check.product else check.error)
"""

import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from textwrap import shorten

import httpx
from sqlalchemy.orm import Session

from . import config, db
from .alerts import find_alerts
from .errors import FetchError, TrackingError
from .fetch import fetch_product
from .models import Item, Listing, ProductInfo
from .prices import format_rupees


@dataclass
class Check:
    """The result of checking one listing."""

    listing: Listing
    product: ProductInfo | None = None              # None when the check failed
    error: str | None = None                        # why it failed
    alerts: list[str] = field(default_factory=list)  # messages of the alerts it made


def track(
    session: Session,
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
    item = None if item_id is None else _item(session, item_id)
    product = fetch_product(link, client)
    existing = db.find_listing(session, product.site, product.product_id)
    if existing:
        raise TrackingError(f"This product is already tracked, as item {existing.item_id}.")

    now = now or db.utc_now()
    with db.transaction(session):
        if item is None:
            item = db.add_item(session, name or product.title or product.product_id, target, now)
        elif target is not None:
            item.target_price = target
        listing = db.add_listing(session, item, product, now)
        return _save(session, listing, product, now)


def check(session: Session, listing: Listing, client: httpx.Client, now: datetime | None = None) -> Check:
    """Fetch one listing's price now and save it, with any alerts it deserves."""
    now = now or db.utc_now()
    try:
        product = fetch_product(listing.url, client)
    except FetchError as error:
        with db.transaction(session):
            db.record_error(listing, str(error), now)
        return Check(listing, error=str(error))

    with db.transaction(session):
        return _save(session, listing, product, now)


def check_all(session: Session, client: httpx.Client, now: datetime | None = None) -> Iterator[Check]:
    """Check every listing of the active items, saving each result as it comes in."""
    for number, listing in enumerate(db.listings_to_check(session)):
        if number:
            time.sleep(config.PAUSE_BETWEEN_PRODUCTS)
        yield check(session, listing, client, now)


def set_target(session: Session, item_id: int, target: Decimal | None) -> None:
    """Change an item's target price; None removes it."""
    item = _item(session, item_id)
    with db.transaction(session):
        item.target_price = target


def untrack(session: Session, item_id: int) -> None:
    """Stop tracking an item, and delete its price history and alerts."""
    item = _item(session, item_id)
    with db.transaction(session):
        session.delete(item)


def _item(session: Session, item_id: int) -> Item:
    item = db.get_item(session, item_id)
    if item is None:
        raise TrackingError(f"There is no item {item_id}.")
    return item


def _save(session: Session, listing: Listing, product: ProductInfo, now: datetime) -> Check:
    """Save a fetched price and make the alerts it deserves. Run it inside db.transaction()."""
    earlier = db.prices_since(session, listing, now - timedelta(days=config.BIG_DROP_DAYS))
    db.record_price(session, listing, product, now)

    result = Check(listing, product)
    if not product.in_stock or product.price is None:
        return result

    item = listing.item
    repeat_window = now - timedelta(days=config.ALERT_REPEAT_DAYS)
    for alert in find_alerts(product.price, item.target_price, earlier):
        sent = db.alert_prices_since(session, listing, alert.kind, repeat_window)
        if any(price <= alert.price for price in sent):
            continue
        name = shorten(item.name, 60, placeholder="…")
        message = f"{name} is {format_rupees(alert.price)} on {listing.site.capitalize()}, {alert.reason}"
        db.add_alert(session, listing, alert.kind, alert.price, message, now)
        result.alerts.append(message)
    return result
