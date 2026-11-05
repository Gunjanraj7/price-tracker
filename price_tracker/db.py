"""Opening the database, and the queries the rest of the app uses.

The database is SQLite by default (config.DB_PATH). Set DATABASE_URL, in the
project's .env file or the environment, to use another one, e.g. PostgreSQL:
    postgresql+psycopg://user:password@host/dbname

connect() brings the tables up to date with Alembic migrations (in
migrations/) before handing back a session, so a new or older database just works.

The functions here don't commit: wrap changes in `with db.transaction(session):`.
"""

import os
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy import URL, Engine, create_engine, event, make_url, select
from sqlalchemy.orm import Session, joinedload, selectinload, sessionmaker
from sqlalchemy.pool import StaticPool

from . import config
from .models import Alert, Item, Listing, PriceCheck, ProductInfo

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"
URL_VARIABLE = "DATABASE_URL"


def database_url() -> str | URL:
    """DATABASE_URL if it's set, otherwise the SQLite file config.DB_PATH."""
    return os.environ.get(URL_VARIABLE, "").strip() or URL.create("sqlite", database=str(config.DB_PATH))


def describe(url: str | URL | None = None) -> str:
    """Which database `url` (database_url() by default) is, for people, without its password."""
    url = make_url(database_url() if url is None else url)
    if url.get_backend_name() == "sqlite":
        return f"SQLite, {url.database or 'in memory'}"
    name = {"postgresql": "PostgreSQL"}.get(url.get_backend_name(), url.get_backend_name())
    return f"{name}, {url.render_as_string(hide_password=True)}"


def make_engine(url: str | URL | None = None, upgrade: bool = True) -> Engine:
    """An engine for the database at `url` (database_url() by default).

    With `upgrade`, the tables are brought up to date first. "sqlite://" is a
    new database in memory, which tests use.
    """
    url = database_url() if url is None else url
    if str(url) in ("sqlite://", "sqlite:///:memory:"):
        # One shared connection, or each would get its own empty database. The web
        # API uses it from several threads, which SQLite allows only when asked.
        engine = create_engine(url, poolclass=StaticPool, connect_args={"check_same_thread": False})
    else:
        engine = create_engine(url)
    if engine.dialect.name == "sqlite":
        # SQLite only enforces foreign keys, and so deletes an item's listings with it, when asked to.
        event.listen(engine, "connect", lambda connection, _: connection.execute("PRAGMA foreign_keys = ON"))
    if upgrade:
        migrate(engine)
    return engine


def migrate(engine: Engine, revision: str = "head") -> None:
    """Bring the tables up to `revision` (the newest by default) with the Alembic migrations."""
    alembic_config = AlembicConfig()
    alembic_config.set_main_option("script_location", str(MIGRATIONS_DIR))
    with engine.begin() as connection:
        alembic_config.attributes["connection"] = connection
        command.upgrade(alembic_config, revision)


class _ClosingSession(Session):
    """A session that also closes its database when it's closed."""

    def close(self) -> None:
        super().close()
        self.bind.dispose()


def connect(url: str | URL | None = None) -> Session:
    """Open the database, with its tables up to date, and return a session on it.

    Close the session when done, or use it with `with`. Objects you got from it
    keep their values after a commit.
    """
    return _ClosingSession(make_engine(url), expire_on_commit=False)


def session_maker(engine: Engine) -> sessionmaker[Session]:
    """Makes sessions on an engine you keep open, like the web API's, one per request."""
    return sessionmaker(engine, expire_on_commit=False)


@contextmanager
def transaction(session: Session) -> Iterator[None]:
    """Commit the changes made inside, or undo them all if something fails."""
    try:
        yield
        session.commit()
    except BaseException:
        session.rollback()
        raise


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


# Items

def add_item(session: Session, name: str, target_price: Decimal | None, now: datetime) -> Item:
    item = Item(name=name, target_price=target_price, active=True, created_at=now)
    session.add(item)
    session.flush()     # gives it its id
    return item


def get_item(session: Session, item_id: int) -> Item | None:
    return session.get(Item, item_id)


def all_items(session: Session) -> list[Item]:
    """Every item, with its listings."""
    return list(session.scalars(select(Item).options(selectinload(Item.listings)).order_by(Item.id)))


# Listings

def add_listing(session: Session, item: Item, product: ProductInfo, now: datetime) -> Listing:
    listing = Listing(
        item=item,
        site=product.site,
        product_id=product.product_id,
        url=product.url,
        title=product.title,
        image_url=product.image_url,
        currency=product.currency,
        created_at=now,
    )
    session.add(listing)
    session.flush()
    return listing


def find_listing(session: Session, site: str, product_id: str) -> Listing | None:
    return session.scalar(select(Listing).where(Listing.site == site, Listing.product_id == product_id))


def listings_to_check(session: Session) -> list[Listing]:
    """The listings of every active item."""
    query = select(Listing).join(Listing.item).where(Item.active).order_by(Listing.item_id, Listing.id)
    return list(session.scalars(query))


# Checks

def record_price(session: Session, listing: Listing, product: ProductInfo, now: datetime) -> None:
    """Save a successful check: add it to the history and make it the listing's latest."""
    session.add(PriceCheck(listing_id=listing.id, price=product.price, in_stock=product.in_stock, checked_at=now))
    if product.title:
        listing.title = product.title
    if product.image_url:
        listing.image_url = product.image_url
    listing.last_price = product.price
    listing.last_in_stock = product.in_stock
    listing.last_checked_at = now
    listing.last_error = None


def record_error(listing: Listing, message: str, now: datetime) -> None:
    """Save a failed check. The last price stays as it was."""
    listing.last_checked_at = now
    listing.last_error = message


def prices_since(session: Session, listing: Listing, since: datetime) -> list[Decimal]:
    """The prices a listing could be bought at, in the checks from `since` on."""
    query = (
        select(PriceCheck.price)
        .where(
            PriceCheck.listing_id == listing.id,
            PriceCheck.checked_at >= since,
            PriceCheck.in_stock,
            PriceCheck.price.is_not(None),
        )
        .order_by(PriceCheck.checked_at)
    )
    return list(session.scalars(query))


def checks_since(session: Session, listing: Listing, since: datetime) -> list[PriceCheck]:
    """Every successful check of a listing from `since` on, oldest first, sold out or not."""
    query = (
        select(PriceCheck)
        .where(PriceCheck.listing_id == listing.id, PriceCheck.checked_at >= since)
        .order_by(PriceCheck.checked_at, PriceCheck.id)
    )
    return list(session.scalars(query))


# Alerts

def add_alert(
    session: Session, listing: Listing, kind: str, price: Decimal, message: str, now: datetime
) -> Alert:
    alert = Alert(listing=listing, kind=kind, price=price, message=message, created_at=now)
    session.add(alert)
    session.flush()
    return alert


def alert_prices_since(session: Session, listing: Listing, kind: str, since: datetime) -> list[Decimal]:
    """The prices of a listing's alerts of one kind, made from `since` on."""
    query = select(Alert.price).where(Alert.listing_id == listing.id, Alert.kind == kind, Alert.created_at >= since)
    return list(session.scalars(query))


def unsent_alerts(session: Session, since: datetime) -> list[Alert]:
    """The alerts made from `since` on that haven't been sent yet, oldest first, with their listings."""
    query = (
        select(Alert)
        .options(joinedload(Alert.listing))
        .where(Alert.sent_at.is_(None), Alert.created_at >= since)
        .order_by(Alert.id)
    )
    return list(session.scalars(query))


def recent_alerts(session: Session, limit: int) -> list[Alert]:
    """The newest alerts first, with their listings and items."""
    query = (
        select(Alert)
        .options(joinedload(Alert.listing).joinedload(Listing.item))
        .order_by(Alert.created_at.desc(), Alert.id.desc())
        .limit(limit)
    )
    return list(session.scalars(query))
