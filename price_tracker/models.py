"""The data the fetcher hands back, and the tables tracked products are saved in.

The tables are SQLAlchemy models, so the same code runs on SQLite (the default)
and PostgreSQL. Changing them needs a migration too: see "Changing the tables"
in the README.

    items           what you track: a name and an optional target price
    listings        an item's page on one store; an item has one per store
    price_history   one row for every successful check of a listing
    alerts          the alerts made so far, so the same one isn't repeated
    users           the accounts that can log in to the web app
    login_sessions  the browsers that are logged in
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, MetaData, Text, UniqueConstraint, true
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator


@dataclass
class PageDetails:
    """What a store parser reads off one product page."""

    title: str | None
    price: Decimal | None           # None when the product can't be bought right now
    in_stock: bool                  # False when sold out or no seller is offering it
    currency: str = "INR"
    product_id: str | None = None   # set when the page knows the exact product better than the link
    image_url: str | None = None    # the product's photo (https), when the page has one


@dataclass
class ProductInfo:
    """A product and its current price."""

    site: str               # "amazon" or "flipkart"
    product_id: str         # ASIN for Amazon, pid for Flipkart
    url: str                # cleaned-up link, same for every user
    title: str | None
    price: Decimal | None   # None when the product can't be bought right now
    currency: str
    in_stock: bool          # False when sold out or no seller is offering it
    image_url: str | None = None    # the product's photo (https), when the page has one


class Money(TypeDecorator):
    """Rupees: a Decimal in Python, whole paise in the database (₹1,299.50 is 129950), so it stays exact."""

    impl = BigInteger
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return None if value is None else int((Decimal(value) * 100).to_integral_value())

    def process_result_value(self, value, dialect):
        return None if value is None else Decimal(value) / 100


class UTCDateTime(TypeDecorator):
    """A moment in time, saved and handed back in UTC.

    SQLite has no time zones, so there it's saved as UTC without one; PostgreSQL
    keeps the zone. Either way you get back a datetime in UTC.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError(f"{value} has no time zone; use db.utc_now() or give one")
        return value.astimezone(timezone.utc)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class Base(DeclarativeBase):
    # Name constraints predictably, so later migrations can refer to them.
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


class Item(Base):
    """Something you track. It has one listing for each store you track it on."""

    __tablename__ = "items"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    target_price: Mapped[Decimal | None] = mapped_column(Money)   # alert when the price gets close; None for no target
    active: Mapped[bool] = mapped_column(default=True, server_default=true())   # False skips it when checking
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)

    # Deleting an item deletes its listings, and their price history and alerts, in the database.
    listings: Mapped[list["Listing"]] = relationship(
        back_populates="item", order_by="Listing.id", cascade="all, delete-orphan", passive_deletes=True
    )


class Listing(Base):
    """An item's page on one store, with the result of its last check."""

    __tablename__ = "listings"
    __table_args__ = (UniqueConstraint("site", "product_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id", ondelete="CASCADE"))
    site: Mapped[str] = mapped_column(Text)                         # "amazon" or "flipkart"
    product_id: Mapped[str] = mapped_column(Text)                   # ASIN for Amazon, pid for Flipkart
    url: Mapped[str] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text)                 # the store's title, updated on every check
    image_url: Mapped[str | None] = mapped_column(Text)             # the store's photo of it, updated on every check
    currency: Mapped[str] = mapped_column(Text)
    last_price: Mapped[Decimal | None] = mapped_column(Money)       # None when it couldn't be bought at the last check
    last_in_stock: Mapped[bool | None]
    last_checked_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    last_error: Mapped[str | None] = mapped_column(Text)            # why the last check failed; None when it worked
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)

    item: Mapped[Item] = relationship(back_populates="listings")


class PriceCheck(Base):
    """One successful check of a listing."""

    __tablename__ = "price_history"
    __table_args__ = (Index("price_history_by_listing", "listing_id", "checked_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id", ondelete="CASCADE"))
    price: Mapped[Decimal | None] = mapped_column(Money)            # None when it couldn't be bought
    in_stock: Mapped[bool]
    checked_at: Mapped[datetime] = mapped_column(UTCDateTime)


class Alert(Base):
    """An alert a check made."""

    __tablename__ = "alerts"
    __table_args__ = (Index("alerts_by_listing", "listing_id", "kind", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(Text)                         # "near_target" or "big_drop"
    price: Mapped[Decimal] = mapped_column(Money)
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)
    sent_at: Mapped[datetime | None] = mapped_column(UTCDateTime)  # None until it's sent to Telegram

    listing: Mapped[Listing] = relationship()


class User(Base):
    """An account that can log in to the web app. Made with `python -m price_tracker user add NAME`."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(Text, unique=True)       # always lowercase
    password_hash: Mapped[str] = mapped_column(Text)               # a scrypt hash (see auth.py), never the password
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)


class LoginSession(Base):
    """A browser that's logged in.

    Its cookie holds a random token; this keeps only the token's SHA-256 hash,
    so the table can't be used to log in. Logging out deletes the row.
    """

    __tablename__ = "login_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(Text, unique=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)

    user: Mapped[User] = relationship()
