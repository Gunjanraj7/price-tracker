"""Everything that can go wrong while fetching a price or tracking a product.

Catch FetchError to handle all fetching problems; the subclasses say what happened.
"""


class TrackingError(Exception):
    """A tracking request that can't be done, like adding a product twice."""


class NotFound(TrackingError):
    """There is no item with that number."""


class AlreadyTracked(TrackingError):
    """The product is tracked already."""


class TooSoon(Exception):
    """Asked again too soon, like a price checked a moment ago. `seconds` says how long to wait."""

    def __init__(self, message: str, seconds: int):
        super().__init__(message)
        self.seconds = seconds


class LoginError(Exception):
    """Base class for login problems."""


class NotLoggedIn(LoginError):
    """The request needs a login, and there's none (or it expired)."""


class WrongPassword(LoginError):
    """The username or the password is wrong."""


class AccountError(Exception):
    """An account can't be made or changed, like a username that's taken or a password that's too short."""


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
