"""How the command line writes times, names and prices."""

from datetime import datetime, timedelta, timezone
from textwrap import shorten

from ..models import Item, Listing
from ..prices import format_rupees

IST = timezone(timedelta(hours=5, minutes=30))


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
