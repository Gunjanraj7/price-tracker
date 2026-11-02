from decimal import Decimal

import httpx
import pytest

from price_tracker import config
from price_tracker.errors import Blocked, FetchError, NetworkError, ParseError, UnsupportedSite
from price_tracker.fetch import fetch_product

AMAZON_LINK = "https://www.amazon.in/dp/B0D3DK779N"


def fake_store(pages):
    """A client whose 'internet' is a dict of url -> (status, html or redirect target).

    A value can also be a function returning (status, body), for pages that
    change between visits. Returns the client and the list of requested urls.
    """
    requests = []

    def handle(request):
        url = str(request.url)
        requests.append(url)
        answer = pages[url]
        status, body = answer() if callable(answer) else answer
        if 300 <= status < 400:
            return httpx.Response(status, headers={"Location": body})
        return httpx.Response(status, text=body)

    client = httpx.Client(transport=httpx.MockTransport(handle), follow_redirects=True)
    return client, requests


def test_follows_share_link_and_cleans_it(page):
    client, _ = fake_store({
        "https://amzn.in/d/abc123": (301, "https://www.amazon.in/boAt/dp/B0D3DK779N?ref=share&tag=x"),
        "https://www.amazon.in/boAt/dp/B0D3DK779N?ref=share&tag=x": (200, page("amazon_buy_box.html")),
    })
    product = fetch_product("Check out this product on Amazon https://amzn.in/d/abc123", client)
    assert (product.site, product.product_id) == ("amazon", "B0D3DK779N")
    assert product.url == AMAZON_LINK
    assert product.price == Decimal("470.50")


def test_requests_the_clean_link(page):
    client, requests = fake_store({AMAZON_LINK: (200, page("amazon_buy_box.html"))})
    fetch_product("https://www.amazon.in/boAt/dp/B0D3DK779N/ref=sr_1_3?keywords=boat&smid=X", client)
    assert requests == [AMAZON_LINK]


def test_uses_flipkart_pid_from_page_when_link_has_none(page):
    link = "https://www.flipkart.com/boat-airdopes-131/p/itma0ea2cce3d648"
    client, _ = fake_store({link: (200, page("flipkart_product.html"))})
    product = fetch_product(link, client)
    assert product.product_id == "ACCHDYCG92CUSJFT"
    assert product.url == link + "?pid=ACCHDYCG92CUSJFT"


def test_retries_when_blocked(page):
    answers = iter([(503, "busy"), (200, page("amazon_browser_check.html")), (200, page("amazon_buy_box.html"))])
    client, requests = fake_store({AMAZON_LINK: lambda: next(answers)})
    product = fetch_product(AMAZON_LINK, client)
    assert product.price == Decimal("470.50")
    assert len(requests) == 3


def test_gives_up_after_retries():
    client, requests = fake_store({AMAZON_LINK: (529, "overloaded")})
    with pytest.raises(Blocked):
        fetch_product(AMAZON_LINK, client)
    assert len(requests) == 1 + config.RETRIES


@pytest.mark.parametrize("status, error", [(500, NetworkError), (404, FetchError), (410, FetchError)])
def test_turns_http_errors_into_fetch_errors(status, error):
    client, _ = fake_store({AMAZON_LINK: (status, "oops")})
    with pytest.raises(error):
        fetch_product(AMAZON_LINK, client)


def test_rejects_other_stores_without_going_online():
    client, requests = fake_store({})
    with pytest.raises(UnsupportedSite):
        fetch_product("https://www.myntra.com/some-shirt/123", client)
    assert requests == []


def test_saves_page_it_could_not_read(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DEBUG_DIR", tmp_path)
    client, _ = fake_store({AMAZON_LINK: (200, "<html>changed</html>")})
    with pytest.raises(ParseError):
        fetch_product(AMAZON_LINK, client)
    assert (tmp_path / "amazon_B0D3DK779N.html").read_text(encoding="utf-8") == "<html>changed</html>"
