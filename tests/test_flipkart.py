from decimal import Decimal

import pytest

from price_tracker.errors import ParseError
from price_tracker.stores.flipkart import parse_page


def test_reads_json_ld(page):
    result = parse_page(page("flipkart_product.html"))
    assert result.title == "boAt Airdopes 131 Gen 2, 13mm Drivers, 70H Battery"
    assert result.price == Decimal("799")
    assert result.in_stock is True


def test_ignores_out_of_stock_labels_of_other_variants(page):
    # "Out of stock" / "Sold Out" on the page belong to other colours, not this one.
    assert parse_page(page("flipkart_product.html")).in_stock is True


def test_json_ld_out_of_stock_has_no_price(page):
    html = page("flipkart_product.html").replace("schema.org/InStock", "schema.org/OutOfStock")
    result = parse_page(html)
    assert result.in_stock is False
    assert result.price is None


def test_reads_pid_from_page(page):
    assert parse_page(page("flipkart_product.html")).product_id == "ACCHDYCG92CUSJFT"


def test_falls_back_to_page_data(page):
    result = parse_page(page("flipkart_page_data_only.html"))
    assert result.price == Decimal("799")      # not the stray ₹1,099
    assert result.in_stock is True
    assert result.title == "Apple iPhone 12 ( 64 GB Storage)"


def test_page_data_out_of_stock_has_no_price(page):
    html = page("flipkart_page_data_only.html").replace('"IN_STOCK"', '"OUT_OF_STOCK"')
    result = parse_page(html)
    assert result.in_stock is False
    assert result.price is None


def test_page_without_product_data_fails():
    with pytest.raises(ParseError):
        parse_page("<html><body><div>Sold Out</div><div>₹1,099</div></body></html>")
