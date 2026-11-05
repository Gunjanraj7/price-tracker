"""The alerts the checks made."""

from typing import Annotated

from fastapi import APIRouter, Query

from ... import db
from ...models import Alert
from ..dependencies import LOGGED_IN, SessionDep
from ..schemas import AlertOut

router = APIRouter(prefix="/api/alerts", tags=["alerts"], dependencies=LOGGED_IN)


@router.get("")
def recent_alerts(
    session: SessionDep, limit: Annotated[int, Query(ge=1, le=500, description="how many")] = 50
) -> list[AlertOut]:
    """The newest alerts first."""
    return [_alert_out(alert) for alert in db.recent_alerts(session, limit)]


def _alert_out(alert: Alert) -> AlertOut:
    listing = alert.listing
    return AlertOut(
        id=alert.id,
        item_id=listing.item_id,
        item_name=listing.item.name,
        site=listing.site,
        kind=alert.kind,
        price=alert.price,
        message=alert.message,
        url=listing.url,
        created_at=alert.created_at,
        sent_at=alert.sent_at,
    )
