"""Flipkart. Product links look like flipkart.com/<name>/p/<itm id>?pid=<pid>.

The pid picks the exact colour/size; the itm id is shared by all of them.
"""

import re
from urllib.parse import parse_qs, urlparse

from bs4 import BeautifulSoup

from ..errors import ParseError, UnsupportedSite
from ..models import PageDetails
from ..prices import parse_price
from .common import check_not_blocked, from_json_ld, select_text

NAME = "flipkart"
DOMAIN = "flipkart.com"
SHORT_LINK_HOSTS = {"dl.flipkart.com", "fkrt.it", "fkrt.cc"}


# ---------------------------------------------------------------- links

def parse_link(url: str) -> tuple[str, str]:
    parts = urlparse(url)
    pid = parse_qs(parts.query).get("pid", [None])[0]
    if pid:
        return pid, link_for(pid, url)
    item = re.search(r"/p/(itm[0-9a-zA-Z]+)", parts.path)
    if not item:
        raise UnsupportedSite(f"Could not find a product ID in this Flipkart link: {url}")
    return item.group(1), f"https://www.flipkart.com{parts.path}"


def link_for(product_id: str, url: str) -> str:
    return f"https://www.flipkart.com{urlparse(url).path}?pid={product_id}"


# ---------------------------------------------------------------- pages

# Flipkart's own page data. Each of these appears once, for the main product.
PAGE_PRICE = re.compile(r'"finalPrice":\s*(\d+(?:\.\d+)?)')
PAGE_STATUS = re.compile(r'"availabilityStatus":\s*"([A-Z_]+)"')
PAGE_PID = re.compile(r'"pageContext":\{.{0,1000}?"fsn":"([A-Z0-9]{16})"')


def _title(soup: BeautifulSoup) -> str | None:
    # og:title reads "<name> Price in India - Buy <name> Online - ... : Flipkart.com"
    # or "Buy <name> Online at Best Price On Flipkart.com".
    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        return re.sub(r"^Buy\s+|\s+(?:Price in India|Online at Best Price)\b.*$", "", og_title["content"]).strip()
    return select_text(soup, "h1")


def parse_page(html: str) -> PageDetails:
    check_not_blocked(html)
    soup = BeautifulSoup(html, "html.parser")

    # Flipkart's CSS class names are random and change often, and the page
    # text mentions "Out of stock" for other colours and sizes, so only the
    # embedded product data is trusted: the schema.org block first, then
    # Flipkart's own page data.
    json_ld = from_json_ld(soup) or {}
    final_price = PAGE_PRICE.search(html)
    status = PAGE_STATUS.search(html)
    pid = PAGE_PID.search(html)

    if json_ld:
        in_stock = json_ld["in_stock"]
    elif status:
        in_stock = status.group(1) == "IN_STOCK"
    else:
        raise ParseError("Could not find the product data on the Flipkart page.")

    price = json_ld.get("price") or (parse_price(final_price.group(1)) if final_price else None)
    if not in_stock:
        # Out-of-stock pages still list the old price; don't treat it as current.
        price = None
    elif not price:
        raise ParseError("Found the product but not its price on the Flipkart page.")

    return PageDetails(
        title=json_ld.get("title") or _title(soup),
        price=price,
        in_stock=in_stock,
        currency=json_ld.get("currency", "INR"),
        # Links without a pid open the default colour/size; this is its pid.
        product_id=pid.group(1) if pid else None,
    )
