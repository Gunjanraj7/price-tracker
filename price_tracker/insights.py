"""What the dashboard shows about each store page, worked out from its price history.

For every listing: the lowest and highest price it could be bought at since
tracking began, its usual price (the middle price of the last BIG_DROP_DAYS
days, as the big-drop alert uses), the price at the check before the latest,
and the recent checks for a small chart. Two queries cover any number of listings.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from statistics import median

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import config
from .models import Listing, PriceCheck


@dataclass
class ListingStats:
    lowest: Decimal | None = None       # since tracking began, among the checks it could be bought at
    highest: Decimal | None = None
    usual: Decimal | None = None        # the middle price of the last config.BIG_DROP_DAYS days
    previous: Decimal | None = None     # at the check before the latest, when both could be bought
    checks: int = 0                     # checks it could be bought at, since tracking began
    recent: list[PriceCheck] = field(default_factory=list)     # the last BIG_DROP_DAYS days, oldest first


def listing_stats(session: Session, listings: list[Listing], now: datetime) -> dict[int, ListingStats]:
    """ListingStats for each of `listings`, by listing id."""
    stats = {listing.id: ListingStats() for listing in listings}
    if not stats:
        return stats

    ids = list(stats)
    totals = (
        select(PriceCheck.listing_id, func.min(PriceCheck.price), func.max(PriceCheck.price), func.count())
        .where(PriceCheck.listing_id.in_(ids), PriceCheck.in_stock, PriceCheck.price.is_not(None))
        .group_by(PriceCheck.listing_id)
    )
    for listing_id, lowest, highest, count in session.execute(totals):
        stats[listing_id].lowest, stats[listing_id].highest, stats[listing_id].checks = lowest, highest, count

    since = now - timedelta(days=config.BIG_DROP_DAYS)
    recent = (
        select(PriceCheck)
        .where(PriceCheck.listing_id.in_(ids), PriceCheck.checked_at >= since)
        .order_by(PriceCheck.listing_id, PriceCheck.checked_at, PriceCheck.id)
    )
    for check in session.scalars(recent):
        stats[check.listing_id].recent.append(check)

    for one in stats.values():
        prices = [check.price for check in one.recent if _buyable(check)]
        one.usual = median(prices) if prices else None
        if len(one.recent) >= 2 and _buyable(one.recent[-1]) and _buyable(one.recent[-2]):
            one.previous = one.recent[-2].price
    return stats


def _buyable(check: PriceCheck) -> bool:
    return check.in_stock and check.price is not None
