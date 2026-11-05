"""Is it running, and are the daily checks on?"""

from datetime import datetime, timezone

from fastapi import APIRouter

from ... import scheduler
from ...errors import ScheduleError
from ..dependencies import LOGGED_IN
from ..schemas import Health, Schedule

router = APIRouter(prefix="/api", tags=["status"])


@router.get("/health")
def health() -> Health:
    """Answers when the API is running. Needs no login."""
    return Health()


@router.get("/schedule", dependencies=LOGGED_IN)
def daily_checks() -> Schedule:
    """Whether the daily checks are on (`python -m price_tracker schedule on`), and when the next one is."""
    try:
        times = scheduler.scheduled_times()
    except ScheduleError:
        return Schedule(available=False, on=False, times=[], next_check=None)
    if not times:
        return Schedule(available=True, on=False, times=[], next_check=None)
    upcoming = scheduler.next_run(times, datetime.now()).astimezone(timezone.utc)   # the task runs in local time
    return Schedule(available=True, on=True, times=[f"{moment:%H:%M}" for moment in times], next_check=upcoming)
