from decimal import Decimal

import pytest

from price_tracker.alerts import BIG_DROP, NEAR_TARGET, find_alerts


def kinds(price, target=None, earlier=()):
    target = None if target is None else Decimal(target)
    return [alert.kind for alert in find_alerts(Decimal(price), target, [Decimal(p) for p in earlier])]


def test_no_target_and_no_history_means_no_alerts():
    assert kinds("999") == []


@pytest.mark.parametrize(
    "price, expected",
    [("1100", []), ("1051", []), ("1050", [NEAR_TARGET]), ("1000", [NEAR_TARGET]), ("800", [NEAR_TARGET])],
)
def test_near_target_means_at_most_5_percent_above_it(price, expected):
    assert kinds(price, target="1000") == expected


def test_says_whether_the_target_is_reached():
    [close] = find_alerts(Decimal("1040"), Decimal("1000"), [])
    [reached] = find_alerts(Decimal("999"), Decimal("1000"), [])
    assert close.reason == "within 5% of your ₹1,000 target"
    assert reached.reason == "at or below your ₹1,000 target"


@pytest.mark.parametrize("price, expected", [("701", []), ("700", [BIG_DROP]), ("500", [BIG_DROP])])
def test_big_drop_means_30_percent_below_the_usual_price(price, expected):
    assert kinds(price, earlier=["1000", "1000", "1000"]) == expected


def test_usual_price_is_the_middle_one_so_a_short_hike_is_ignored():
    # ₹1,000 most of the time, raised to ₹2,000 for a day before a "sale".
    earlier = [Decimal(p) for p in ["1000", "1000", "2000", "2000", "1000"]]
    assert find_alerts(Decimal("1000"), None, earlier) == []
    [alert] = find_alerts(Decimal("650"), None, earlier)
    assert alert.reason == "35% below its usual ₹1,000"


def test_can_be_near_target_and_a_big_drop_at_once():
    assert kinds("690", target="700", earlier=["1000"]) == [NEAR_TARGET, BIG_DROP]
