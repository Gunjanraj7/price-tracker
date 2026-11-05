"""The shapes of the web API's requests and answers.

Prices are rupees, sent as JSON numbers (1299.5). Times are ISO 8601 in UTC
("2026-11-05T03:30:00Z"). FastAPI checks requests against these and shows them
in the API docs at /docs.
"""

from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer

# Prices are exact Decimals inside the app, and plain numbers in JSON.
Rupees = Annotated[Decimal, PlainSerializer(float, return_type=float, when_used="json")]
NewPrice = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2, examples=[1499])]
Link = Annotated[
    str,
    Field(
        min_length=1,
        description="An Amazon.in or Flipkart product link, a short share link, or the whole message the store app shares",
        examples=["https://www.amazon.in/dp/B0D3DK779N"],
    ),
]


class FromModel(BaseModel):
    """A schema that can be filled in from a database model."""

    model_config = ConfigDict(from_attributes=True)


class PricePoint(FromModel):
    checked_at: datetime
    price: Rupees | None = Field(description="null when it couldn't be bought")
    in_stock: bool


class ListingStats(BaseModel):
    """What the price history says about a store page."""

    lowest_price: Rupees | None = Field(description="the lowest price it could be bought at since tracking began")
    highest_price: Rupees | None = Field(description="the highest, likewise")
    usual_price: Rupees | None = Field(description="the middle price of the last 30 days of checks")
    previous_price: Rupees | None = Field(description="the price at the check before the latest one")
    checks: int = Field(description="how many checks found a price it could be bought at")
    recent_prices: list[PricePoint] = Field(description="the last 30 days of checks, oldest first, for a small chart")


class ListingOut(FromModel):
    """An item's page on one store, with the result of its last check."""

    id: int
    site: str = Field(description='"amazon" or "flipkart"')
    product_id: str = Field(description="ASIN for Amazon, pid for Flipkart")
    url: str
    title: str | None
    image_url: str | None = Field(description="the store's photo of the product")
    last_price: Rupees | None = Field(description="null when it couldn't be bought at the last check")
    last_in_stock: bool | None
    last_checked_at: datetime | None
    last_error: str | None = Field(description="why the last check failed; null when it worked")
    stats: ListingStats | None = None


class ItemOut(FromModel):
    """Something you track, with its page on each store."""

    id: int
    name: str
    target_price: Rupees | None
    active: bool = Field(description="false when the daily checks skip it")
    created_at: datetime
    listings: list[ListingOut]


class NewItem(BaseModel):
    link: Link
    target_price: NewPrice | None = Field(None, description="alert when the price gets close to this")
    name: str | None = Field(None, min_length=1, max_length=200, description="your own name; the store's title by default")


class NewListing(BaseModel):
    link: Link = Field(description="the same product's page on the other store")


class ItemChanges(BaseModel):
    """Only the fields you send are changed."""

    target_price: NewPrice | None = Field(None, description="null removes the target")


class ListingError(BaseModel):
    listing_id: int
    site: str
    error: str


class CheckResult(BaseModel):
    """An item after adding or checking it."""

    item: ItemOut
    alerts: list[str] = Field(description="the alerts this made; they also go to Telegram when it's set up")
    errors: list[ListingError] = Field(description="the store pages that couldn't be checked")


class ListingHistory(BaseModel):
    listing_id: int
    site: str
    prices: list[PricePoint] = Field(description="oldest first")


class AlertOut(BaseModel):
    id: int
    item_id: int
    item_name: str
    site: str
    kind: str = Field(description='"near_target" or "big_drop"')
    price: Rupees
    message: str
    url: str
    created_at: datetime
    sent_at: datetime | None = Field(description="when it was sent to Telegram; null if it wasn't")


class Health(BaseModel):
    status: str = "ok"


class LoginDetails(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=200)


class LoginStatus(BaseModel):
    logged_in: bool
    username: str | None = Field(description="who is logged in; null when no one is")
    has_accounts: bool = Field(
        description="false until an account is made, with `python -m price_tracker user add NAME`"
    )


class Schedule(BaseModel):
    """The daily checks, made by Windows Task Scheduler (`python -m price_tracker schedule on`)."""

    available: bool = Field(description="false where there's no Windows Task Scheduler, like a Linux server")
    on: bool
    times: list[str] = Field(description='the times of day it checks at, like "09:00"')
    next_check: datetime | None
