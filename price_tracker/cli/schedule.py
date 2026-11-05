"""Checking prices every day: schedule on, schedule off, and whether it's on."""

import argparse
from datetime import datetime

from .. import config, scheduler
from ..errors import ScheduleError
from .logfile import last_logged_check


def run(args: argparse.Namespace) -> int:
    """Turn the daily checks on or off, or say whether they're on."""
    if args.times and args.action != "on":
        print("Error:    times only go with on, like: schedule on 9:00 21:00")
        return 1
    try:
        if args.action == "on":
            times = args.times or [scheduler.parse_time(text) for text in config.CHECK_TIMES]
            scheduler.turn_on(times)
            print(f"Daily checks are on: every day at {scheduler.describe(times)}.")
            print(f"Each check adds what it found to {config.LOG_PATH}")
            print("Turn them off with: python -m price_tracker schedule off")
            return 0
        if args.action == "off":
            print("Daily checks are off." if scheduler.turn_off() else "Daily checks were already off.")
            return 0
        times = scheduler.scheduled_times()
    except ScheduleError as error:
        print(f"Error:    {error}")
        return 1

    if times is None:
        print("Daily checks are off. Turn them on with: python -m price_tracker schedule on")
        return 0
    if not times:
        print("The daily check task is there but has no times. Run: python -m price_tracker schedule on")
        return 1
    upcoming = scheduler.next_run(times, datetime.now())
    print(f"Daily checks are on: every day at {scheduler.describe(times)}.")
    print(f"Next check: {upcoming:%d %b, %I:%M %p}")
    print(f"Last check: {last_logged_check() or 'none yet'}")
    print(f"Log:        {config.LOG_PATH}")
    return 0
