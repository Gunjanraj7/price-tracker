from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import text

from price_tracker import db, tracking
from price_tracker.errors import Blocked, TrackingError

AMAZON = "https://www.amazon.in/dp/B0D3DK779N"
FLIPKART = "https://www.flipkart.com/boat-airdopes-131/p/itma0ea2cce3d648?pid=ACCHDYCG92CUSJFT"

START = datetime(2026, 11, 4, 3, 30, tzinfo=timezone.utc)   # 9 AM in India
HALF_DAY = timedelta(hours=12)


def check_at(session, moment):
    """Check everything as if it were `moment`, and return the alert messages."""
    return [message for result in tracking.check_all(session, None, now=moment) for message in result.alerts]


def price_checks(session):
    return session.scalar(text("SELECT COUNT(*) FROM price_history"))


def test_track_saves_the_item_and_its_first_price(session, store):
    store[AMAZON] = "1299"
    result = tracking.track(session, AMAZON, None, target=Decimal("1000"), now=START)

    [item] = db.all_items(session)
    assert (item.name, item.target_price, item.active) == ("boAt Airdopes 131", Decimal("1000"), True)
    [listing] = item.listings
    assert (listing.site, listing.product_id, listing.url) == ("amazon", "B0D3DK779N", AMAZON)
    assert (listing.last_price, listing.last_in_stock, listing.last_checked_at) == (Decimal("1299"), True, START)
    assert db.prices_since(session, listing, START) == [Decimal("1299")]
    assert result.alerts == []


def test_track_reads_the_real_page(session, page, fake_store):
    client, _ = fake_store({AMAZON: (200, page("amazon_buy_box.html"))})
    tracking.track(session, AMAZON, client, name="Earbuds")
    [item] = db.all_items(session)
    assert item.name == "Earbuds"
    assert item.listings[0].last_price == Decimal("470.50")


def test_the_other_stores_link_joins_the_same_item(session, store):
    store[AMAZON], store[FLIPKART] = "1299", "1249"
    tracking.track(session, AMAZON, None, now=START)
    tracking.track(session, FLIPKART, None, item_id=1, target=Decimal("1100"), now=START)

    [item] = db.all_items(session)
    assert item.target_price == Decimal("1100")
    assert [listing.site for listing in item.listings] == ["amazon", "flipkart"]


def test_a_product_cannot_be_tracked_twice(session, store):
    store[AMAZON] = "1299"
    tracking.track(session, AMAZON, None, now=START)
    with pytest.raises(TrackingError, match="already tracked, as item 1"):
        tracking.track(session, AMAZON, None, now=START)
    assert len(db.all_items(session)) == 1


def test_adding_to_a_missing_item_fails_before_going_online(session, store):
    with pytest.raises(TrackingError, match="no item 7"):
        tracking.track(session, AMAZON, None, item_id=7)   # store has no prices: fetching would fail


def test_check_saves_every_listing(session, store):
    store[AMAZON], store[FLIPKART] = "1299", "1249"
    tracking.track(session, AMAZON, None, now=START)
    tracking.track(session, FLIPKART, None, item_id=1, now=START)

    store[AMAZON], store[FLIPKART] = "1199", None
    results = list(tracking.check_all(session, None, now=START + HALF_DAY))

    assert [result.product.price for result in results] == [Decimal("1199"), None]
    amazon, flipkart = db.get_item(session, 1).listings
    assert amazon.last_price == Decimal("1199")
    assert (flipkart.last_price, flipkart.last_in_stock) == (None, False)
    assert price_checks(session) == 4


def test_a_failed_check_keeps_the_last_price(session, store):
    store[AMAZON] = "1299"
    tracking.track(session, AMAZON, None, now=START)

    store[AMAZON] = Blocked("The store refused the request (HTTP 503).")
    [result] = tracking.check_all(session, None, now=START + HALF_DAY)
    assert result.error == "The store refused the request (HTTP 503)."
    [listing] = db.get_item(session, 1).listings
    assert (listing.last_price, listing.last_checked_at) == (Decimal("1299"), START + HALF_DAY)
    assert listing.last_error == "The store refused the request (HTTP 503)."
    assert price_checks(session) == 1

    store[AMAZON] = "1299"
    check_at(session, START + 2 * HALF_DAY)
    assert listing.last_error is None


def test_paused_items_are_not_checked(session, store):
    store[AMAZON] = "1299"
    tracking.track(session, AMAZON, None, now=START)
    with db.transaction(session):
        db.get_item(session, 1).active = False
    assert list(tracking.check_all(session, None)) == []


def test_near_target_alert_is_not_repeated_until_the_price_falls_further(session, store):
    store[AMAZON] = "1299"
    tracking.track(session, AMAZON, None, target=Decimal("1000"), now=START)

    store[AMAZON] = "1040"
    assert check_at(session, START + HALF_DAY) == [
        "boAt Airdopes 131 is ₹1,040 on Amazon, within 5% of your ₹1,000 target"
    ]
    assert check_at(session, START + 2 * HALF_DAY) == []    # same price
    store[AMAZON] = "1060"
    assert check_at(session, START + 3 * HALF_DAY) == []    # not close any more
    store[AMAZON] = "1040"
    assert check_at(session, START + 4 * HALF_DAY) == []    # close again, but not cheaper than the alert
    store[AMAZON] = "990"
    assert check_at(session, START + 5 * HALF_DAY) == [
        "boAt Airdopes 131 is ₹990 on Amazon, at or below your ₹1,000 target"
    ]


def test_an_alert_comes_back_after_a_week(session, store):
    store[AMAZON] = "990"
    assert len(tracking.track(session, AMAZON, None, target=Decimal("1000"), now=START).alerts) == 1
    assert check_at(session, START + timedelta(days=6)) == []
    assert len(check_at(session, START + timedelta(days=7, hours=1))) == 1


def test_big_drop_alert(session, store):
    store[AMAZON] = "2000"
    tracking.track(session, AMAZON, None, now=START)
    for day in range(1, 4):
        check_at(session, START + timedelta(days=day))

    store[AMAZON] = "1399"
    assert check_at(session, START + timedelta(days=4)) == [
        "boAt Airdopes 131 is ₹1,399 on Amazon, 30% below its usual ₹2,000"
    ]


def test_big_drop_only_looks_at_the_last_30_days(session, store):
    store[AMAZON] = "2000"
    tracking.track(session, AMAZON, None, now=START)
    store[AMAZON] = "1300"
    assert check_at(session, START + timedelta(days=31)) == []


def test_set_target_and_untrack(session, store):
    store[AMAZON] = "1299"
    tracking.track(session, AMAZON, None, now=START)

    tracking.set_target(session, 1, Decimal("900"))
    assert db.get_item(session, 1).target_price == Decimal("900")
    tracking.set_target(session, 1, None)
    assert db.get_item(session, 1).target_price is None

    tracking.untrack(session, 1)
    assert db.all_items(session) == []
    assert price_checks(session) == 0
    with pytest.raises(TrackingError):
        tracking.untrack(session, 1)
