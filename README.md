# Price Tracker

Gets the current price of Amazon.in and Flipkart products from their links.

## Setup

```
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Run

From the project folder:

```
.venv\Scripts\python.exe -m price_tracker                        # paste links one at a time
.venv\Scripts\python.exe -m price_tracker "<link>" "<link>" ...  # or give them up front
```

A link can be a product link, a share link (`amzn.in/d/…`, `dl.flipkart.com/s/…`)
or the whole message the store app shares. Put links in quotes: they often contain `&`.

From other Python code:

```python
from price_tracker import fetch_product

product = fetch_product("https://www.amazon.in/dp/B088FKCD4J")
print(product.title, product.price, product.in_stock)
```

## Tests

```
.venv\Scripts\python.exe -m pytest
```

The tests are offline and use the sample pages in `tests/pages/`.

## Layout

```
price_tracker/
    __init__.py      what other code imports: fetch_product, ProductInfo, errors
    __main__.py      makes `python -m price_tracker` work
    cli.py           the command line (printing, asking for links)
    fetch.py         downloads a page, retries, hands it to the right store
    links.py         finds the link in pasted text and works out the store
    models.py        ProductInfo and PageDetails
    errors.py        FetchError and its subclasses
    prices.py        reading "₹1,299.00" and writing ₹1,29,999
    config.py        timeouts, retries, pauses, debug folder
    stores/
        __init__.py  the list of stores
        common.py    helpers every store uses (CAPTCHA check, schema.org data)
        amazon.py    Amazon.in links and pages
        flipkart.py  Flipkart links and pages
tests/
    pages/           sample HTML pages
    test_*.py        one test file per module
```

**Adding a store:** write `stores/<store>.py` with the same names as `amazon.py`
(`NAME`, `DOMAIN`, `SHORT_LINK_HOSTS`, `parse_link`, `link_for`, `parse_page`),
add it to `STORES` in `stores/__init__.py`, and add sample pages and tests.

**When a store changes its page:** the fetcher fails instead of guessing, and
saves the page to `debug/`. Open it, fix the store's module, and copy the page
into `tests/pages/` as a new test.
