"""What you can type on the command line."""

import argparse
import re
from datetime import time
from decimal import Decimal

from .. import config, scheduler
from ..prices import parse_price

# The words that start a command. Anything else is a link to look up.
COMMANDS = ("add", "list", "check", "target", "remove", "telegram", "schedule", "serve", "user", "-h", "--help")


def price_arg(text: str) -> Decimal | None:
    """Read a price typed on the command line, like 1500, 1,499.50 or ₹60,000. "off" means none."""
    if text.strip().lower() == "off":
        return None
    cleaned = re.sub(r"^(₹|rs\.?)\s*", "", text.strip(), flags=re.IGNORECASE)
    if not re.fullmatch(r"\d[\d,]*(\.\d{1,2})?", cleaned):
        raise argparse.ArgumentTypeError(f"{text!r} is not a price; write it like 1500 or 1,499.50")
    price = parse_price(cleaned)
    if not price:
        raise argparse.ArgumentTypeError("the price must be more than ₹0")
    return price


def time_arg(text: str) -> time:
    """Read a time of day typed on the command line, like 9:00 or 21:30."""
    try:
        return scheduler.parse_time(text)
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m price_tracker",
        description="Track Amazon.in and Flipkart prices. Give links without a command to just see their prices.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    add = commands.add_parser("add", help="start tracking a product")
    add.add_argument("link")
    add.add_argument("--target", type=price_arg, help="alert when the price gets close to this, e.g. 1500")
    add.add_argument("--name", help="your own name for it (default: the store's title)")
    add.add_argument("--to", type=int, metavar="ITEM", help="add the link to item ITEM, e.g. its page on the other store")

    commands.add_parser("list", help="show tracked items and their latest prices")
    check = commands.add_parser("check", help="check every tracked item now and show alerts")
    check.add_argument(
        "--log", action="store_true", help="add the output to logs/check.log instead of showing it (the daily check uses this)"
    )

    target = commands.add_parser("target", help="change an item's target price")
    target.add_argument("item", type=int)
    target.add_argument("price", type=price_arg, help='e.g. 1500, or "off" for no target')

    remove = commands.add_parser("remove", help="stop tracking an item and delete its history")
    remove.add_argument("item", type=int)

    commands.add_parser("telegram", help="set up Telegram alerts: find your chat ID, then send a test message")

    schedule = commands.add_parser("schedule", help="check prices every day, with Windows Task Scheduler")
    schedule.add_argument("action", nargs="?", choices=("on", "off"), help="leave it out to see whether daily checks are on")
    schedule.add_argument(
        "times", nargs="*", type=time_arg, metavar="TIME",
        help=f"with on: when to check, e.g. 8:30 20:30 (default: {' '.join(config.CHECK_TIMES)})",
    )

    serve = commands.add_parser("serve", help="run the web app and its API at http://127.0.0.1:8000")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument(
        "--host", default="127.0.0.1",
        help="who can reach it: 127.0.0.1 (the default) is only this computer. Others would use plain HTTP.",
    )
    serve.add_argument("--reload", action="store_true", help="restart when the code changes, while developing")

    user = commands.add_parser("user", help="make or change the accounts that log in to the web app")
    user.add_argument("action", choices=("add", "password", "list"), help="add an account, change its password, or list them")
    user.add_argument("name", nargs="?", help="the account's username, for add and password")
    return parser
