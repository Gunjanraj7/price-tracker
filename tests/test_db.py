from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import URL, text
from sqlalchemy.exc import IntegrityError, StatementError

from price_tracker import config, db
from price_tracker.models import Base, ProductInfo

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
def session():
    with db.connect("sqlite://") as session:
        yield session


def count(session, table):
    return session.scalar(text(f"SELECT COUNT(*) FROM {table}"))


def test_creates_the_tables_once_and_keeps_the_data(tmp_path):
    url = URL.create("sqlite", database=str(tmp_path / "test.db"))
    with db.connect(url) as session, db.transaction(session):
        db.add_item(session, "Earbuds", None, NOW)
    with db.connect(url) as session:     # the migrations run again and change nothing
        assert [item.name for item in db.all_items(session)] == ["Earbuds"]
        assert session.scalar(text("SELECT version_num FROM alembic_version")) == "0001"


def test_uses_the_sqlite_file_unless_database_url_is_set(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "default.db")
    with db.connect():
        pass
    assert (tmp_path / "default.db").exists()

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'other.db').as_posix()}")
    with db.connect():
        pass
    assert (tmp_path / "other.db").exists()


def test_migrations_match_the_models(session):
    """If this fails, a model changed without a migration: see "Changing the tables" in the README."""
    with session.bind.connect() as connection:
        assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []


def test_prices_stay_exact(session):
    item = db.add_item(session, "Earbuds", Decimal("1199.99"), NOW)
    listing = db.add_listing(session, item, product(), NOW)
    db.record_price(session, listing, product("1299.50"), NOW)
    session.commit()
    session.expire_all()    # read everything back from the database

    assert session.scalar(text("SELECT price FROM price_history")) == 129950
    assert db.find_listing(session, "amazon", "B0D3DK779N").last_price == Decimal("1299.50")
    assert db.get_item(session, item.id).target_price == Decimal("1199.99")


def test_times_are_saved_in_utc(session):
    india = timezone(timedelta(hours=5, minutes=30))
    item = db.add_item(session, "Earbuds", None, datetime(2026, 11, 4, 9, 0, tzinfo=india))
    session.commit()
    session.expire_all()

    assert session.scalar(text("SELECT created_at FROM items")).startswith("2026-11-04 03:30:00")
    assert item.created_at == NOW
    assert item.created_at.tzinfo == timezone.utc


def test_times_need_a_time_zone(session):
    with pytest.raises(StatementError, match="has no time zone"):
        db.add_item(session, "Earbuds", None, datetime(2026, 11, 4, 9, 0))


def test_the_same_product_cannot_be_listed_twice(session):
    item = db.add_item(session, "Earbuds", None, NOW)
    db.add_listing(session, item, product(), NOW)
    with pytest.raises(IntegrityError):
        db.add_listing(session, item, product(), NOW)


def test_deleting_an_item_deletes_its_listings_history_and_alerts(session):
    item = db.add_item(session, "Earbuds", None, NOW)
    listing = db.add_listing(session, item, product(), NOW)
    db.record_price(session, listing, product(), NOW)
    db.add_alert(session, listing, "near_target", Decimal("1299.50"), "Cheap now", NOW)
    session.commit()

    session.delete(item)
    session.commit()
    for table in ("items", "listings", "price_history", "alerts"):
        assert count(session, table) == 0
