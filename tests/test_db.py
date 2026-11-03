import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from price_tracker import db
from price_tracker.models import ProductInfo

NOW = datetime(2026, 11, 4, 3, 30, tzinfo=timezone.utc)


def product(price="1299.50"):
    return ProductInfo(
        site="amazon",
        product_id="B0D3DK779N",
        url="https://www.amazon.in/dp/B0D3DK779N",
        title="boAt Airdopes 131",
        price=Decimal(price),
        currency="INR",
        in_stock=True,
    )


@pytest.fixture
def conn():
    with closing(db.connect(":memory:")) as conn:
        yield conn


def test_creates_the_tables_once_and_keeps_the_data(tmp_path):
    path = tmp_path / "test.db"
    with closing(db.connect(path)) as conn, conn:
        db.add_item(conn, "Earbuds", None, NOW)
    with closing(db.connect(path)) as conn:
        assert [item.name for item in db.all_items(conn)] == ["Earbuds"]
        assert conn.execute("PRAGMA user_version").fetchone()[0] == db.SCHEMA_VERSION


def test_prices_stay_exact(conn):
    item_id = db.add_item(conn, "Earbuds", Decimal("1199.99"), NOW)
    listing_id = db.add_listing(conn, item_id, product(), NOW)
    db.record_price(conn, listing_id, product("1299.50"), NOW)

    assert conn.execute("SELECT price FROM price_history").fetchone()[0] == 129950
    assert db.get_listing(conn, listing_id).last_price == Decimal("1299.50")
    assert db.get_item(conn, item_id).target_price == Decimal("1199.99")


def test_times_are_saved_in_utc(conn):
    india = timezone(timedelta(hours=5, minutes=30))
    item_id = db.add_item(conn, "Earbuds", None, datetime(2026, 11, 4, 9, 0, tzinfo=india))
    assert conn.execute("SELECT created_at FROM items").fetchone()[0] == "2026-11-04T03:30:00+00:00"
    assert db.get_item(conn, item_id).created_at == NOW


def test_the_same_product_cannot_be_listed_twice(conn):
    item_id = db.add_item(conn, "Earbuds", None, NOW)
    db.add_listing(conn, item_id, product(), NOW)
    with pytest.raises(sqlite3.IntegrityError):
        db.add_listing(conn, item_id, product(), NOW)


def test_deleting_an_item_deletes_its_listings_history_and_alerts(conn):
    item_id = db.add_item(conn, "Earbuds", None, NOW)
    listing_id = db.add_listing(conn, item_id, product(), NOW)
    db.record_price(conn, listing_id, product(), NOW)
    db.add_alert(conn, listing_id, "near_target", Decimal("1299.50"), "Cheap now", NOW)

    db.delete_item(conn, item_id)
    for table in ("items", "listings", "price_history", "alerts"):
        assert conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0
