"""Deciding when a price is worth telling you about.

There are two kinds of alert, with their limits in config.py:
    near_target  the price is at or below your target, or at most
                 NEAR_TARGET_PERCENT above it
    big_drop     the price is BIG_DROP_PERCENT or more below its usual price:
                 the middle price of the checks in the last BIG_DROP_DAYS days

The big drop is measured against the prices we recorded, not the store's
"M.R.P." discount, because many products are "40% off" all year round.
Taking the middle price, not the highest, means a short price hike before
a sale doesn't make the sale look bigger than it is.
"""

from dataclasses import dataclass
from decimal import Decimal
from statistics import median

from . import config
from .prices import format_rupees

NEAR_TARGET = "near_target"
BIG_DROP = "big_drop"


@dataclass
class Alert:
    kind: str       # NEAR_TARGET or BIG_DROP
    price: Decimal
    reason: str     # e.g. "within 5% of your ₹60,000 target"


def find_alerts(price: Decimal, target: Decimal | None, earlier_prices: list[Decimal]) -> list[Alert]:
    """The alerts a price deserves.

    `target` is the item's target price, `earlier_prices` the prices the
    listing was on sale for in the last BIG_DROP_DAYS days, before this check.
    """
    found = []

    if target is not None:
        margin = Decimal(str(config.NEAR_TARGET_PERCENT))
        if price <= target:
            found.append(Alert(NEAR_TARGET, price, f"at or below your {format_rupees(target)} target"))
        elif price * 100 <= target * (100 + margin):
            reason = f"within {config.NEAR_TARGET_PERCENT}% of your {format_rupees(target)} target"
            found.append(Alert(NEAR_TARGET, price, reason))

    usual = median(earlier_prices) if earlier_prices else None
    if usual:
        drop = (usual - price) / usual * 100
        if drop >= Decimal(str(config.BIG_DROP_PERCENT)):
            found.append(Alert(BIG_DROP, price, f"{int(drop)}% below its usual {format_rupees(usual)}"))

    return found
