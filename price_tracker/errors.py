"""Everything that can go wrong while fetching a price or tracking a product.

Catch FetchError to handle all fetching problems; the subclasses say what happened.
"""


class TrackingError(Exception):
    """A tracking request that can't be done, like adding a product twice."""


class NotifyError(Exception):
    """An alert could not be sent, or Telegram isn't set up right."""


class ScheduleError(Exception):
    """The scheduled check could not be turned on or off."""


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
