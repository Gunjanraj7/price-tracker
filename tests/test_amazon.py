from decimal import Decimal

import pytest

from price_tracker.errors import Blocked, ParseError
from price_tracker.stores.amazon import parse_page


def test_reads_price_to_pay_not_mrp_or_other_products(page):
    result = parse_page(page("amazon_product.html"))
    assert result.title == "boAt Airdopes 131 (Active Black)"
    assert result.price == Decimal("1899")
    assert result.in_stock is True


def test_reads_buy_box_price(page):
    assert parse_page(page("amazon_buy_box.html")).price == Decimal("470.50")


def test_joins_whole_and_fraction_parts(page):
    assert parse_page(page("amazon_split_price.html")).price == Decimal("12499.50")


def test_falls_back_to_hidden_price(page):
    assert parse_page(page("amazon_hidden_price.html")).price == Decimal("549")


def test_out_of_stock_has_no_price(page):
    result = parse_page(page("amazon_out_of_stock.html"))
    assert result.in_stock is False
    assert result.price is None


def test_without_featured_seller_is_unavailable(page):
    result = parse_page(page("amazon_no_featured_seller.html"))
    assert result.title == "boAt Airdopes 131 Gen 2"
    assert result.in_stock is False
    assert result.price is None


@pytest.mark.parametrize("name", ["amazon_captcha.html", "amazon_browser_check.html"])
def test_captcha_and_browser_check_are_reported_as_blocked(page, name):
    with pytest.raises(Blocked):
        parse_page(page(name))


def test_page_without_product_fails():
    with pytest.raises(ParseError):
        parse_page("<html><body>Something else</body></html>")


def test_product_without_price_fails(page):
    # Better to fail (and save the page) than to guess a price.
    with pytest.raises(ParseError):
        parse_page(page("amazon_out_of_stock.html").replace("Currently unavailable.", "In stock"))
