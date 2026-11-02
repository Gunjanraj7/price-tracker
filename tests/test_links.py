import pytest

from price_tracker.errors import UnsupportedSite
from price_tracker.links import find_link, identify, is_share_link


@pytest.mark.parametrize(
    "url, expected",
    [
        (
            "https://www.amazon.in/Apple-iPhone-15-128-GB/dp/B0CHX1W1XY/ref=sr_1_1?keywords=iphone&tag=abc-21",
            ("amazon", "B0CHX1W1XY", "https://www.amazon.in/dp/B0CHX1W1XY"),
        ),
        (
            "https://www.amazon.in/gp/product/B09XYZ1234?psc=1",
            ("amazon", "B09XYZ1234", "https://www.amazon.in/dp/B09XYZ1234"),
        ),
        (
            # The mobile site has a different layout, so always use www.
            "https://m.amazon.in/dp/B088FKCD4J",
            ("amazon", "B088FKCD4J", "https://www.amazon.in/dp/B088FKCD4J"),
        ),
        (
            "https://www.flipkart.com/apple-iphone-15/p/itm6ac6485515ae4?pid=MOBGTAGPTB3VS24W&lid=LST123&marketplace=FLIPKART",
            (
                "flipkart",
                "MOBGTAGPTB3VS24W",
                "https://www.flipkart.com/apple-iphone-15/p/itm6ac6485515ae4?pid=MOBGTAGPTB3VS24W",
            ),
        ),
        (
            "https://www.flipkart.com/apple-iphone-15/p/itm6ac6485515ae4?lid=LST123",
            ("flipkart", "itm6ac6485515ae4", "https://www.flipkart.com/apple-iphone-15/p/itm6ac6485515ae4"),
        ),
    ],
)
def test_identify_cleans_links(url, expected):
    assert identify(url) == expected


@pytest.mark.parametrize(
    "url",
    [
        "https://www.myntra.com/some-shirt/123",
        "https://www.amazon.com/dp/B0CHX1W1XY",          # prices would be in dollars
        "https://www.amazon.in.example.com/dp/B0CHX1W1XY",
        "https://www.amazon.in/gp/cart/view.html",
        "https://www.flipkart.com/search?q=airdopes",
    ],
)
def test_identify_rejects_other_links(url):
    with pytest.raises(UnsupportedSite):
        identify(url)


@pytest.mark.parametrize(
    "text, expected",
    [
        ("https://www.amazon.in/dp/B088FKCD4J", "https://www.amazon.in/dp/B088FKCD4J"),
        ("  https://www.amazon.in/dp/B088FKCD4J  \n", "https://www.amazon.in/dp/B088FKCD4J"),
        ("Check out this product on Amazon https://amzn.in/d/abc123", "https://amzn.in/d/abc123"),
        ("Have a look at boAt Airdopes on Flipkart https://dl.flipkart.com/s/Xy9AbCuuuN.",
         "https://dl.flipkart.com/s/Xy9AbCuuuN"),
        ("www.flipkart.com/x/p/itm123?pid=ABC", "https://www.flipkart.com/x/p/itm123?pid=ABC"),
    ],
)
def test_find_link(text, expected):
    assert find_link(text) == expected


def test_find_link_without_link():
    with pytest.raises(UnsupportedSite):
        find_link("airdopes 131")


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://amzn.in/d/abc123", True),
        ("https://dl.flipkart.com/s/Xy9AbCuuuN", True),
        ("https://www.amazon.in/dp/B088FKCD4J", False),
    ],
)
def test_is_share_link(url, expected):
    assert is_share_link(url) is expected
