"""Turning whatever the user pasted into a clean product link."""

import re
from urllib.parse import urlparse

from .errors import UnsupportedSite
from .stores import STORES


def find_link(text: str) -> str:
    """Pick the link out of whatever was pasted.

    The store apps share messages like 'Check out this product on Amazon
    https://amzn.in/d/abc123', and people often paste links without https://.
    """
    match = re.search(r"https?://\S+", text)
    if match:
        return match.group(0).rstrip(".,;)")
    word = text.strip()
    if re.fullmatch(r"\S+\.\S+", word):
        return "https://" + word
    raise UnsupportedSite(f"No link found in: {word!r}")


def is_share_link(url: str) -> bool:
    """Share links only redirect to the product, so they can't be identified up front."""
    host = urlparse(url).hostname or ""
    return any(host in store.SHORT_LINK_HOSTS for store in STORES.values())


def _on_domain(host: str, domain: str) -> bool:
    return host == domain or host.endswith("." + domain)


def identify(url: str) -> tuple[str, str, str]:
    """Work out which store a link is from, its product ID and a clean link.

    Returns (site, product_id, clean_url). Raises UnsupportedSite otherwise.
    """
    host = urlparse(url).hostname or ""
    for store in STORES.values():
        if _on_domain(host, store.DOMAIN):
            return (store.NAME, *store.parse_link(url))

    if "amazon." in host:
        raise UnsupportedSite(f"Only amazon.in links are supported, got: {host}")
    supported = " and ".join(store.DOMAIN for store in STORES.values())
    raise UnsupportedSite(f"Only links from {supported} are supported, got: {host or url}")
