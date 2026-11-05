"""Amazon.in. Product links look like amazon.in/<name>/dp/<ASIN>."""

import re
from decimal import Decimal
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Tag

from ..errors import ParseError, UnsupportedSite
from ..models import PageDetails
from ..prices import parse_price
from .common import check_not_blocked, from_json_ld, image_link, select_text

NAME = "amazon"
DOMAIN = "amazon.in"
SHORT_LINK_HOSTS = {"amzn.in", "amzn.to"}

ASIN = re.compile(
    r"/(?:dp|gp/product|gp/aw/d|exec/obidos/asin)/([A-Z0-9]{10})(?:/|$)", re.IGNORECASE
)


# ---------------------------------------------------------------- links

def parse_link(url: str) -> tuple[str, str]:
    match = ASIN.search(urlparse(url).path)
    if not match:
        raise UnsupportedSite(f"Could not find a product ID in this Amazon link: {url}")
    asin = match.group(1).upper()
    return asin, link_for(asin, url)


def link_for(product_id: str, url: str) -> str:
    # The mobile site has a different layout, so always use www.
    return f"https://www.amazon.in/dp/{product_id}"


# ---------------------------------------------------------------- pages

# Where Amazon shows the price you would actually pay. Prices anywhere else
# on the page belong to the M.R.P., other formats (Kindle, hardcover) or
# other products in the "similar items" carousels.
PRICE_AREAS = (
    "#corePriceDisplay_desktop_feature_div",
    "#corePrice_feature_div",
    "#corePrice_desktop",
    "#apex_desktop",
)
PRICE_TO_PAY = (".priceToPay", ".apexPriceToPay", ".apex-pricetopay-value")

UNAVAILABLE = ("currently unavailable", "out of stock", "available from these sellers")


def _read_price_tag(tag: Tag) -> Decimal | None:
    """Read one Amazon price element.

    The full price is normally in a hidden '.a-offscreen' span, but that
    span is sometimes empty and the price is only shown split into whole
    rupees and paise.
    """
    price = parse_price(select_text(tag, ".a-offscreen"))
    if price:
        return price
    whole = re.sub(r"\D", "", select_text(tag, ".a-price-whole") or "")
    if not whole:
        return None
    paise = re.sub(r"\D", "", select_text(tag, ".a-price-fraction") or "")
    return Decimal(f"{whole}.{paise}" if paise else whole)


def find_price(soup: BeautifulSoup) -> Decimal | None:
    for area in PRICE_AREAS:
        selector = ", ".join(f"{area} {cls}" for cls in PRICE_TO_PAY)
        for tag in soup.select(selector):
            price = _read_price_tag(tag)
            if price:
                return price

    # Older page layouts.
    for selector in ("#priceblock_dealprice", "#priceblock_ourprice", "#price_inside_buybox"):
        price = parse_price(select_text(soup, selector))
        if price:
            return price

    # A hidden copy of the selected product's price.
    hidden = soup.select_one("#twister-plus-price-data-price")
    return parse_price(hidden.get("value")) if hidden else None


def find_image(soup: BeautifulSoup) -> str | None:
    """The main product photo: its 300-pixel version, or the big one when that's a placeholder.

    Books show theirs as #imgBlkFront. A missing photo is fine: the web app shows a placeholder.
    """
    photo = soup.select_one("#landingImage") or soup.select_one("#imgBlkFront")
    if photo is None:
        return None
    return image_link(photo.get("src")) or image_link(photo.get("data-old-hires"))


def parse_page(html: str) -> PageDetails:
    check_not_blocked(html)
    soup = BeautifulSoup(html, "html.parser")

    title = select_text(soup, "#productTitle")
    availability = (select_text(soup, "#availability") or "").lower()
    unavailable = any(phrase in availability for phrase in UNAVAILABLE)
    price = None if unavailable else find_price(soup)

    if not price and not unavailable:
        json_ld = from_json_ld(soup)
        if json_ld:
            title = title or json_ld["title"]
            unavailable = not json_ld["in_stock"]
            price = None if unavailable else json_ld["price"]

    # No price and only a "See All Buying Options" button: no seller is
    # featured, so there is no single price to report.
    if not price and title and soup.select_one("#buybox-see-all-buying-choices"):
        unavailable = True

    if not title and not price:
        raise ParseError("This does not look like an Amazon product page.")
    if not price and not unavailable:
        raise ParseError("Found the product but not its price on the Amazon page.")

    return PageDetails(title=title, price=price, in_stock=not unavailable, image_url=find_image(soup))
