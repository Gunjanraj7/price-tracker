"""Everything that can go wrong while fetching a price.

Catch FetchError to handle all of them; the subclasses say what happened.
"""


class FetchError(Exception):
    """Base class for everything that can go wrong while fetching a price."""


class UnsupportedSite(FetchError):
    """The link is not a product page from a store we support."""


class Blocked(FetchError):
    """The store showed a CAPTCHA or refused the request."""


class NetworkError(FetchError):
    """The store could not be reached, or had a problem of its own."""


class ParseError(FetchError):
    """The page loaded, but we could not find the price on it."""
