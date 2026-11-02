from decimal import Decimal

import pytest

from price_tracker.prices import format_rupees, parse_price


@pytest.mark.parametrize(
    "text, expected",
    [
        ("₹1,29,999.00", Decimal("129999.00")),
        ("₹ 499", Decimal("499")),
        ("Rs. 2,499", Decimal("2499")),
        ("79,900.", Decimal("79900")),
        ("", None),
        ("Price not available", None),
    ],
)
def test_parse_price(text, expected):
    assert parse_price(text) == expected


@pytest.mark.parametrize(
    "amount, expected",
    [
        (Decimal("899"), "₹899"),
        (Decimal("1299.00"), "₹1,299"),
        (Decimal("129999.5"), "₹1,29,999.50"),
        (Decimal("12345678"), "₹1,23,45,678"),
    ],
)
def test_format_rupees(amount, expected):
    assert format_rupees(amount) == expected
