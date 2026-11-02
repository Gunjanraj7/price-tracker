"""The data the fetcher hands back."""

from dataclasses import dataclass
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
