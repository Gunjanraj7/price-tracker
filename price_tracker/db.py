"""Saving tracked products, their price history and alerts in SQLite.

The database is one file, config.DB_PATH, with four tables:
    items          what you track: a name and an optional target price
    listings       an item's page on one store; an item has one per store
    price_history  one row for every successful check of a listing
    alerts         the alerts made so far, so the same one isn't repeated

Prices are stored as whole paise (₹1,299.50 -> 129950) so they stay exact,
and times as UTC text ("2026-11-04T05:30:00+00:00"). The functions here
take and return Decimal rupees and datetimes. They don't commit: wrap
changes in `with conn:`.
"""

import sqlite3
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from . import config
from .models import Item, Listing, ProductInfo

# Raise this and add the changes to connect() when the tables change,
# so existing databases are updated instead of rebuilt.
SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE items (
    id            INTEGER PRIMARY KEY,
    name          TEXT NOT NULL,
    target_price  INTEGER,                      -- paise; NULL for no target
    active        INTEGER NOT NULL DEFAULT 1,   -- 0 skips it when checking
    created_at    TEXT NOT NULL
);

CREATE TABLE listings (
    id               INTEGER PRIMARY KEY,
    item_id          INTEGER NOT NULL REFERENCES items (id) ON DELETE CASCADE,
    site             TEXT NOT NULL,             -- "amazon" or "flipkart"
    product_id       TEXT NOT NULL,             -- ASIN for Amazon, pid for Flipkart
    url              TEXT NOT NULL,
    title            TEXT,
    currency         TEXT NOT NULL,
    last_price       INTEGER,                   -- paise; NULL when it couldn't be bought
    last_in_stock    INTEGER,
    last_checked_at  TEXT,
    last_error       TEXT,                      -- NULL when the last check worked
    created_at       TEXT NOT NULL,
    UNIQUE (site, product_id)
);

CREATE TABLE price_history (
    id          INTEGER PRIMARY KEY,
    listing_id  INTEGER NOT NULL REFERENCES listings (id) ON DELETE CASCADE,
    price       INTEGER,                        -- paise; NULL when it couldn't be bought
    in_stock    INTEGER NOT NULL,
    checked_at  TEXT NOT NULL
);
CREATE INDEX price_history_by_listing ON price_history (listing_id, checked_at);

CREATE TABLE alerts (
    id          INTEGER PRIMARY KEY,
    listing_id  INTEGER NOT NULL REFERENCES listings (id) ON DELETE CASCADE,
    kind        TEXT NOT NULL,                  -- "near_target" or "big_drop"
    price       INTEGER NOT NULL,               -- paise
    message     TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    sent_at     TEXT                            -- NULL until a notification is sent
);
CREATE INDEX alerts_by_listing ON alerts (listing_id, kind, created_at);
"""


def connect(path: Path | str | None = None) -> sqlite3.Connection:
    """Open the database (config.DB_PATH by default), creating it the first time."""
    conn = sqlite3.connect(config.DB_PATH if path is None else path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    if conn.execute("PRAGMA user_version").fetchone()[0] == 0:
        conn.executescript(f"BEGIN; {SCHEMA} PRAGMA user_version = {SCHEMA_VERSION}; COMMIT;")
    return conn


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _stamp(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).isoformat(timespec="seconds")


def _moment(stamp: str | None) -> datetime | None:
    return datetime.fromisoformat(stamp) if stamp else None


def _paise(rupees: Decimal | None) -> int | None:
    return None if rupees is None else int((rupees * 100).to_integral_value())


def _rupees(paise: int | None) -> Decimal | None:
    return None if paise is None else Decimal(paise) / 100


def _item(row: sqlite3.Row) -> Item:
    return Item(
        id=row["id"],
        name=row["name"],
        target_price=_rupees(row["target_price"]),
        active=bool(row["active"]),
        created_at=_moment(row["created_at"]),
    )


def _listing(row: sqlite3.Row) -> Listing:
    return Listing(
        id=row["id"],
        item_id=row["item_id"],
        site=row["site"],
        product_id=row["product_id"],
        url=row["url"],
        title=row["title"],
        currency=row["currency"],
        last_price=_rupees(row["last_price"]),
        last_in_stock=bool(row["last_in_stock"]),
        last_checked_at=_moment(row["last_checked_at"]),
        last_error=row["last_error"],
    )


# Items

def add_item(conn: sqlite3.Connection, name: str, target_price: Decimal | None, now: datetime) -> int:
    cursor = conn.execute(
        "INSERT INTO items (name, target_price, created_at) VALUES (?, ?, ?)",
        (name, _paise(target_price), _stamp(now)),
    )
    return cursor.lastrowid


def get_item(conn: sqlite3.Connection, item_id: int) -> Item | None:
    row = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    return _item(row) if row else None


def all_items(conn: sqlite3.Connection) -> list[Item]:
    return [_item(row) for row in conn.execute("SELECT * FROM items ORDER BY id")]


def set_target(conn: sqlite3.Connection, item_id: int, target_price: Decimal | None) -> None:
    conn.execute("UPDATE items SET target_price = ? WHERE id = ?", (_paise(target_price), item_id))


def delete_item(conn: sqlite3.Connection, item_id: int) -> None:
    """Delete an item with its listings, price history and alerts."""
    conn.execute("DELETE FROM items WHERE id = ?", (item_id,))


# Listings

def add_listing(conn: sqlite3.Connection, item_id: int, product: ProductInfo, now: datetime) -> int:
    cursor = conn.execute(
        "INSERT INTO listings (item_id, site, product_id, url, title, currency, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (item_id, product.site, product.product_id, product.url, product.title, product.currency, _stamp(now)),
    )
    return cursor.lastrowid


def get_listing(conn: sqlite3.Connection, listing_id: int) -> Listing | None:
    row = conn.execute("SELECT * FROM listings WHERE id = ?", (listing_id,)).fetchone()
    return _listing(row) if row else None


def find_listing(conn: sqlite3.Connection, site: str, product_id: str) -> Listing | None:
    row = conn.execute(
        "SELECT * FROM listings WHERE site = ? AND product_id = ?", (site, product_id)
    ).fetchone()
    return _listing(row) if row else None


def listings_of(conn: sqlite3.Connection, item_id: int) -> list[Listing]:
    rows = conn.execute("SELECT * FROM listings WHERE item_id = ? ORDER BY id", (item_id,))
    return [_listing(row) for row in rows]


def listings_to_check(conn: sqlite3.Connection) -> list[Listing]:
    """The listings of every active item."""
    rows = conn.execute(
        "SELECT listings.* FROM listings JOIN items ON items.id = listings.item_id"
        " WHERE items.active ORDER BY listings.item_id, listings.id"
    )
    return [_listing(row) for row in rows]


# Checks

def record_price(conn: sqlite3.Connection, listing_id: int, product: ProductInfo, now: datetime) -> None:
    """Save a successful check: add it to the history and make it the listing's latest."""
    price, in_stock, stamp = _paise(product.price), int(product.in_stock), _stamp(now)
    conn.execute(
        "INSERT INTO price_history (listing_id, price, in_stock, checked_at) VALUES (?, ?, ?, ?)",
        (listing_id, price, in_stock, stamp),
    )
    conn.execute(
        "UPDATE listings SET title = COALESCE(?, title), last_price = ?, last_in_stock = ?,"
        " last_checked_at = ?, last_error = NULL WHERE id = ?",
        (product.title, price, in_stock, stamp, listing_id),
    )


def record_error(conn: sqlite3.Connection, listing_id: int, message: str, now: datetime) -> None:
    """Save a failed check. The last price stays as it was."""
    conn.execute(
        "UPDATE listings SET last_checked_at = ?, last_error = ? WHERE id = ?",
        (_stamp(now), message, listing_id),
    )


def prices_since(conn: sqlite3.Connection, listing_id: int, since: datetime) -> list[Decimal]:
    """The prices a listing could be bought at, in the checks from `since` on."""
    rows = conn.execute(
        "SELECT price FROM price_history WHERE listing_id = ? AND checked_at >= ?"
        " AND in_stock AND price IS NOT NULL ORDER BY checked_at",
        (listing_id, _stamp(since)),
    )
    return [_rupees(row["price"]) for row in rows]


# Alerts

def add_alert(
    conn: sqlite3.Connection, listing_id: int, kind: str, price: Decimal, message: str, now: datetime
) -> int:
    cursor = conn.execute(
        "INSERT INTO alerts (listing_id, kind, price, message, created_at) VALUES (?, ?, ?, ?, ?)",
        (listing_id, kind, _paise(price), message, _stamp(now)),
    )
    return cursor.lastrowid


def alert_prices_since(conn: sqlite3.Connection, listing_id: int, kind: str, since: datetime) -> list[Decimal]:
    """The prices of a listing's alerts of one kind, made from `since` on."""
    rows = conn.execute(
        "SELECT price FROM alerts WHERE listing_id = ? AND kind = ? AND created_at >= ?",
        (listing_id, kind, _stamp(since)),
    )
    return [_rupees(row["price"]) for row in rows]
