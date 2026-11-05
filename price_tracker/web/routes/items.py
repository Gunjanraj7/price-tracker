"""Tracked items: add them, change their target, check them now, remove them, and their price history."""

import logging
import math
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Query, Request, Response, status
from sqlalchemy.orm import Session, sessionmaker

from ... import config, db, insights, notify, tracking
from ...errors import NotifyError, TooSoon
from ...models import Item
from ...tracking import Check
from ..dependencies import LOGGED_IN, ClientDep, SessionDep
from ..errors import wait_text
from ..schemas import (
    CheckResult,
    ItemChanges,
    ItemOut,
    ListingError,
    ListingHistory,
    ListingStats,
    NewItem,
    NewListing,
    PricePoint,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/items", tags=["items"], dependencies=LOGGED_IN)


@router.get("")
def list_items(session: SessionDep) -> list[ItemOut]:
    """Every tracked item, with its latest price on each store and what its price history says."""
    return items_out(session, db.all_items(session))


@router.post("", status_code=status.HTTP_201_CREATED)
def add_item(
    new: NewItem, session: SessionDep, client: ClientDep, request: Request, background: BackgroundTasks
) -> CheckResult:
    """Start tracking a product, and save its price now. This reads the store page, so it takes a few seconds."""
    result = tracking.track(session, new.link, client, target=new.target_price, name=new.name)
    return _check_result(session, result.listing.item, [result], request, background)


@router.get("/{item_id}")
def get_item(item_id: int, session: SessionDep) -> ItemOut:
    return items_out(session, [tracking.find_item(session, item_id)])[0]


@router.patch("/{item_id}")
def change_item(item_id: int, changes: ItemChanges, session: SessionDep) -> ItemOut:
    """Change an item's target price. Send `"target_price": null` to remove it."""
    item = tracking.find_item(session, item_id)
    if "target_price" in changes.model_fields_set:
        item = tracking.set_target(session, item_id, changes.target_price)
    return items_out(session, [item])[0]


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(item_id: int, session: SessionDep) -> Response:
    """Stop tracking an item, and delete its price history and alerts."""
    tracking.untrack(session, item_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{item_id}/listings", status_code=status.HTTP_201_CREATED)
def add_listing(
    item_id: int,
    new: NewListing,
    session: SessionDep,
    client: ClientDep,
    request: Request,
    background: BackgroundTasks,
) -> CheckResult:
    """Add the same product's page on another store to an item."""
    result = tracking.track(session, new.link, client, item_id=item_id)
    return _check_result(session, result.listing.item, [result], request, background)


@router.post("/{item_id}/check")
def check_item(
    item_id: int, session: SessionDep, client: ClientDep, request: Request, background: BackgroundTasks
) -> CheckResult:
    """Check an item's prices now, on every store, and save them. Takes a few seconds per store.

    A store page checked less than 5 minutes ago is skipped, to go easy on the
    stores; when every one was, the answer is 429, with Retry-After.
    """
    item = tracking.find_item(session, item_id)
    now = db.utc_now()
    waits = {listing.id: tracking.wait_before_checking(listing, now) for listing in item.listings}
    due = [listing for listing in item.listings if not waits[listing.id]]
    if item.listings and not due:
        seconds = max(1, math.ceil(min(waits.values()).total_seconds()))
        raise TooSoon(
            f"Checked less than {config.CHECK_AGAIN_AFTER_MINUTES} minutes ago. "
            f"To go easy on the stores, try again in {wait_text(seconds)}.",
            seconds,
        )
    results = list(tracking.check_listings(session, due, client))
    return _check_result(session, item, results, request, background)


@router.get("/{item_id}/history")
def price_history(
    item_id: int,
    session: SessionDep,
    days: Annotated[int, Query(ge=1, le=3650, description="how far back to go")] = 30,
) -> list[ListingHistory]:
    """The prices recorded for each of an item's store pages, oldest first, for a chart."""
    item = tracking.find_item(session, item_id)
    since = db.utc_now() - timedelta(days=days)
    return [
        ListingHistory(
            listing_id=listing.id,
            site=listing.site,
            prices=[PricePoint.model_validate(check) for check in db.checks_since(session, listing, since)],
        )
        for listing in item.listings
    ]


def items_out(session: Session, items: list[Item]) -> list[ItemOut]:
    """Items as the API answers them, with what each store page's price history says."""
    stats = insights.listing_stats(session, [listing for item in items for listing in item.listings], db.utc_now())
    answers = []
    for item in items:
        answer = ItemOut.model_validate(item)
        for listing in answer.listings:
            found = stats[listing.id]
            listing.stats = ListingStats(
                lowest_price=found.lowest,
                highest_price=found.highest,
                usual_price=found.usual,
                previous_price=found.previous,
                checks=found.checks,
                recent_prices=[PricePoint.model_validate(check) for check in found.recent],
            )
        answers.append(answer)
    return answers


def _check_result(
    session: Session, item: Item, results: list[Check], request: Request, background: BackgroundTasks
) -> CheckResult:
    """The answer to adding or checking an item. New alerts go to Telegram after it's sent."""
    alerts = [message for result in results for message in result.alerts]
    if alerts:
        background.add_task(send_alerts, request.app.state.sessions)
    return CheckResult(
        item=items_out(session, [item])[0],
        alerts=alerts,
        errors=[
            ListingError(listing_id=result.listing.id, site=result.listing.site, error=result.error)
            for result in results
            if result.error
        ],
    )


def send_alerts(sessions: sessionmaker[Session]) -> None:
    """Send the alerts not sent yet to Telegram, if it's set up."""
    telegram = notify.from_environment()
    if telegram is None:
        return
    with sessions() as session, telegram:
        try:
            notify.send_alerts(session, telegram)
        except NotifyError as error:
            log.warning("Telegram: couldn't send alerts. %s They'll be tried again on the next check.", error)
