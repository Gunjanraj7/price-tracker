"""Command line: see prices now, or track products and get alerts.

Usage, from the project folder:
    python -m price_tracker                          asks you to paste links, one at a time
    python -m price_tracker "<link>" ["<link>" ...]  shows their prices now, without saving them

    python -m price_tracker add "<link>" [--target PRICE] [--name NAME]
                                                     starts tracking a product
    python -m price_tracker add "<link>" --to ITEM   adds another store's page to item ITEM
    python -m price_tracker list                     shows tracked items and their latest prices
    python -m price_tracker check [--log]            checks every tracked item now and shows alerts
                                                     (--log: adds the output to logs/check.log instead)
    python -m price_tracker target ITEM PRICE        changes an item's target price ("off" removes it)
    python -m price_tracker remove ITEM              stops tracking an item and deletes its history
    python -m price_tracker telegram                 sets up Telegram alerts: finds your chat ID,
                                                     then sends a test message
    python -m price_tracker schedule on [TIME ...]   checks every day at 9:00 and 21:00, or the TIMEs
    python -m price_tracker schedule off             stops the daily checks
    python -m price_tracker schedule                 says whether daily checks are on
    python -m price_tracker serve [--port 8000]      runs the web app and its API at http://127.0.0.1:8000
    python -m price_tracker user add NAME            makes an account to log in to the web app with
    python -m price_tracker user password NAME       changes its password (and logs it out everywhere)
    python -m price_tracker user list                shows the accounts

Tracked items are saved in the database DATABASE_URL names (in .env or the
environment), or else in price_tracker.db in the project folder. When
Telegram is set up, `add` and `check` also send their alerts there.

A link can be a normal product link, a short share link (amzn.in/d/...,
dl.flipkart.com/s/...) or the whole message the store app shares.
In PowerShell or cmd, put links in quotes: they often contain '&'.

Each group of commands has a module with a run(args) that does it:
    products.py   seeing prices, and add, list, check, target, remove
    accounts.py   user add / password / list
    telegram.py   telegram
    schedule.py   schedule on / off, and whether it's on
    serve.py      serve
and parser.py says what you can type, output.py how things are written,
logfile.py what --log does.
"""

import argparse
import sys

from .. import envfile
from . import accounts, logfile, products, schedule, serve, telegram
from .parser import COMMANDS, build_parser

HANDLERS = {
    "telegram": telegram.run,
    "schedule": schedule.run,
    "serve": serve.run,
    "user": accounts.run,
}


def run(args: argparse.Namespace) -> int:
    """Run one command typed on the command line. Returns its exit code."""
    return HANDLERS.get(args.command, products.run)(args)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    # Windows terminals can choke on the ₹ sign without this. Under pythonw.exe,
    # as the daily check runs, there is no terminal at all.
    if sys.stdout is not None:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    envfile.load()      # DATABASE_URL and other settings from .env, for every command

    if not args or args[0] not in COMMANDS:
        return products.show_links(args)
    parsed = build_parser().parse_args(args)
    if getattr(parsed, "log", False):
        return logfile.run_logged(lambda: run(parsed))
    return run(parsed)
