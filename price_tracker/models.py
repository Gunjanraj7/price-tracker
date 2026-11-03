"""The data the fetcher hands back, and the tracked products it saves."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass
class PageDetails:
    """What a store parser reads off one product page."""

    title: str | None
    price: Decimal | None           # None when the product can't be bought right now
    in_stock: bool                  # False when sold out or no seller is offering it
    currency: str = "INR"
    product_id: str | None = None   # set when the page knows the exact product better than the link


@dataclass
class ProductInfo:
    """A product and its current price."""

    site: str               # "amazon" or "flipkart"
    product_id: str         # ASIN for Amazon, pid for Flipkart
    url: str                # cleaned-up link, same for every user
    title: str | None
    price: Decimal | None   # None when the product can't be bought right now
    currency: str
    in_stock: bool          # False when sold out or no seller is offering it


@dataclass
class Item:
    """Something you track. It has one listing for each store you track it on."""

    id: int
    name: str
    target_price: Decimal | None    # alert when the price gets close to this; None for no target
    active: bool                    # False skips it when checking
    created_at: datetime


@dataclass
class Listing:
    """An item's page on one store, with the result of its last check."""

    id: int
    item_id: int
    site: str                       # "amazon" or "flipkart"
    product_id: str                 # ASIN for Amazon, pid for Flipkart
    url: str
    title: str | None               # the store's title, updated on every check
    currency: str
    last_price: Decimal | None      # None when it couldn't be bought at the last check
    last_in_stock: bool
    last_checked_at: datetime
    last_error: str | None          # why the last check failed; None when it worked
