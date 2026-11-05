"""Downloading product pages and reading their prices."""

import math
import threading
import time
from contextlib import nullcontext

import httpx

from . import config
from .errors import Blocked, FetchError, NetworkError, ParseError
from .links import find_link, identify, is_share_link
from .models import ProductInfo
from .stores import STORES

# Look like a normal browser visit. Without these headers most stores
# return an error page straight away.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-IN,en;q=0.9",
}


# Store requests go one at a time, at least config.PAUSE_BETWEEN_PRODUCTS
# seconds apart, even when the web app checks several things at once, so
# the stores see a person browsing rather than a burst of requests.
_one_at_a_time = threading.Lock()
_last_request = -math.inf       # time.monotonic() when the last store request ended


def new_client(timeout: float = config.REQUEST_TIMEOUT) -> httpx.Client:
    """An HTTP client that looks like a normal browser visit."""
    return httpx.Client(headers=HEADERS, follow_redirects=True, timeout=timeout)


def fetch_product(link: str, client: httpx.Client | None = None, retries: int = config.RETRIES) -> ProductInfo:
    """Download a product page and read its title and current price.

    `link` can be a product link, a share link, or a whole pasted share
    message. Pass `client` to reuse one connection for several products.
    Blocks and network errors are retried, with a growing pause.
    """
    url = find_link(link)
    # Reject other stores' links before going online. Share links only
    # show the product after their redirect, so those are checked later.
    if not is_share_link(url):
        url = identify(url)[2]

    with (nullcontext(client) if client else new_client()) as client:
        for attempt in range(retries + 1):
            try:
                return _fetch_once(url, client)
            except (Blocked, NetworkError):
                if attempt == retries:
                    raise
                time.sleep(config.RETRY_DELAY * 2**attempt)


def _get_politely(url: str, client: httpx.Client) -> httpx.Response:
    """GET a store page when it's our turn: after any other store request, and the pause after it."""
    global _last_request
    with _one_at_a_time:
        wait = _last_request + config.PAUSE_BETWEEN_PRODUCTS - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        try:
            return client.get(url)
        finally:
            _last_request = time.monotonic()


def _fetch_once(url: str, client: httpx.Client) -> ProductInfo:
    try:
        response = _get_politely(url, client)
    except httpx.HTTPError as error:
        raise NetworkError(f"Could not reach the store: {error}") from error

    status = response.status_code
    if status in (403, 429, 503, 529):
        raise Blocked(f"The store refused the request (HTTP {status}). Try again in a few minutes.")
    if status == 404:
        raise FetchError("The store says this product page does not exist (HTTP 404).")
    if status >= 500:
        raise NetworkError(f"The store had a problem of its own (HTTP {status}).")
    if status >= 400:
        raise FetchError(f"The store returned an error (HTTP {status}).")

    site, product_id, clean_url = identify(str(response.url))
    store = STORES[site]

    try:
        details = store.parse_page(response.text)
    except ParseError:
        # Keep the page so you can open it and see what changed.
        config.DEBUG_DIR.mkdir(exist_ok=True)
        (config.DEBUG_DIR / f"{site}_{product_id}.html").write_text(response.text, encoding="utf-8")
        raise

    # Use the ID the page reports, so the same product always gets the same ID.
    if details.product_id and details.product_id != product_id:
        product_id = details.product_id
        clean_url = store.link_for(product_id, clean_url)

    return ProductInfo(
        site=site,
        product_id=product_id,
        url=clean_url,
        title=details.title,
        price=details.price,
        currency=details.currency,
        in_stock=details.in_stock,
        image_url=details.image_url,
    )
