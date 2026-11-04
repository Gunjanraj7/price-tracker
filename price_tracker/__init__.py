"""Track the prices of Amazon.in and Flipkart products.

The main entry point is fetch_product(): give it a link, get a ProductInfo.

    from price_tracker import fetch_product
    product = fetch_product("https://www.amazon.in/dp/B088FKCD4J")
    print(product.title, product.price)
"""

from .errors import (
    AlreadyTracked,
    Blocked,
    FetchError,
    NetworkError,
    NotFound,
    NotifyError,
    ParseError,
    ScheduleError,
    TrackingError,
    UnsupportedSite,
)
from .fetch import fetch_product, new_client
from .models import ProductInfo
from .prices import format_rupees

__all__ = [
    "AlreadyTracked",
    "Blocked",
    "FetchError",
    "NetworkError",
    "NotFound",
    "NotifyError",
    "ParseError",
    "ProductInfo",
    "ScheduleError",
    "TrackingError",
    "UnsupportedSite",
    "fetch_product",
    "format_rupees",
    "new_client",
]
