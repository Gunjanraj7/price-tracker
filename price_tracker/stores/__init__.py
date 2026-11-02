"""The stores we can read prices from.

Each store is a module with:
    NAME                       short name, e.g. "amazon"
    DOMAIN                     links on this domain (or its subdomains) belong to the store
    SHORT_LINK_HOSTS           share-link hosts that redirect to the store's product pages
    parse_link(url)            -> (product_id, clean_url); raises UnsupportedSite
    link_for(product_id, url)  -> the clean link for that product ID
    parse_page(html)           -> PageDetails; raises Blocked or ParseError

To support a new store, write a module like amazon.py and add it to STORES.
"""

from . import amazon, flipkart

STORES = {store.NAME: store for store in (amazon, flipkart)}
