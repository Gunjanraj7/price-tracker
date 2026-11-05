import math
from decimal import Decimal

import pytest

from price_tracker import config, fetch
from price_tracker.errors import Blocked, FetchError, NetworkError, ParseError, UnsupportedSite
from price_tracker.fetch import fetch_product

AMAZON_LINK = "https://www.amazon.in/dp/B0D3DK779N"


def test_follows_share_link_and_cleans_it(page, fake_store):
    client, _ = fake_store({
        "https://amzn.in/d/abc123": (301, "https://www.amazon.in/boAt/dp/B0D3DK779N?ref=share&tag=x"),
        "https://www.amazon.in/boAt/dp/B0D3DK779N?ref=share&tag=x": (200, page("amazon_buy_box.html")),
    })
    product = fetch_product("Check out this product on Amazon https://amzn.in/d/abc123", client)
    assert (product.site, product.product_id) == ("amazon", "B0D3DK779N")
    assert product.url == AMAZON_LINK
    assert product.price == Decimal("470.50")


def test_requests_the_clean_link(page, fake_store):
    client, requests = fake_store({AMAZON_LINK: (200, page("amazon_buy_box.html"))})
    fetch_product("https://www.amazon.in/boAt/dp/B0D3DK779N/ref=sr_1_3?keywords=boat&smid=X", client)
    assert requests == [AMAZON_LINK]


def test_uses_flipkart_pid_from_page_when_link_has_none(page, fake_store):
    link = "https://www.flipkart.com/boat-airdopes-131/p/itma0ea2cce3d648"
    client, _ = fake_store({link: (200, page("flipkart_product.html"))})
    product = fetch_product(link, client)
    assert product.product_id == "ACCHDYCG92CUSJFT"
    assert product.url == link + "?pid=ACCHDYCG92CUSJFT"


def test_retries_when_blocked(page, fake_store):
    answers = iter([(503, "busy"), (200, page("amazon_browser_check.html")), (200, page("amazon_buy_box.html"))])
    client, requests = fake_store({AMAZON_LINK: lambda: next(answers)})
    product = fetch_product(AMAZON_LINK, client)
    assert product.price == Decimal("470.50")
    assert len(requests) == 3


def test_gives_up_after_retries(fake_store):
    client, requests = fake_store({AMAZON_LINK: (529, "overloaded")})
    with pytest.raises(Blocked):
        fetch_product(AMAZON_LINK, client)
    assert len(requests) == 1 + config.RETRIES


@pytest.mark.parametrize("status, error", [(500, NetworkError), (404, FetchError), (410, FetchError)])
def test_turns_http_errors_into_fetch_errors(status, error, fake_store):
    client, _ = fake_store({AMAZON_LINK: (status, "oops")})
    with pytest.raises(error):
        fetch_product(AMAZON_LINK, client)


def test_rejects_other_stores_without_going_online(fake_store):
    client, requests = fake_store({})
    with pytest.raises(UnsupportedSite):
        fetch_product("https://www.myntra.com/some-shirt/123", client)
    assert requests == []


def test_hands_on_the_product_photo(page, fake_store):
    client, _ = fake_store({AMAZON_LINK: (200, page("amazon_product.html"))})
    assert fetch_product(AMAZON_LINK, client).image_url.startswith("https://m.media-amazon.com/images/I/")


def test_store_requests_wait_their_turn(page, fake_store, monkeypatch):
    """Even several checks at once reach the stores one by one, PAUSE_BETWEEN_PRODUCTS apart."""
    monkeypatch.setattr(config, "PAUSE_BETWEEN_PRODUCTS", 3.0)
    monkeypatch.setattr(fetch, "_last_request", -math.inf)
    waits = []
    monkeypatch.setattr(fetch.time, "sleep", waits.append)
    client, requests = fake_store({AMAZON_LINK: (200, page("amazon_buy_box.html"))})

    fetch_product(AMAZON_LINK, client)
    assert waits == []                  # the first request goes straight away
    fetch_product(AMAZON_LINK, client)
    assert len(requests) == 2
    [wait] = waits
    assert 2.5 < wait <= 3.0


def test_saves_page_it_could_not_read(tmp_path, monkeypatch, fake_store):
    monkeypatch.setattr(config, "DEBUG_DIR", tmp_path)
    client, _ = fake_store({AMAZON_LINK: (200, "<html>changed</html>")})
    with pytest.raises(ParseError):
        fetch_product(AMAZON_LINK, client)
    assert (tmp_path / "amazon_B0D3DK779N.html").read_text(encoding="utf-8") == "<html>changed</html>"
