"""Shared test setup.

All tests are offline: they use the small sample pages in tests/pages,
which copy the structure of real Amazon.in and Flipkart pages (checked
November 2026), cut down to the parts the fetcher reads.
"""

from pathlib import Path

import httpx
import pytest

from price_tracker import config

PAGES = Path(__file__).parent / "pages"


@pytest.fixture
def page():
    """Load a sample page from tests/pages by file name."""
    return lambda name: (PAGES / name).read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def no_waiting(monkeypatch):
    """Never sleep between retries in tests."""
    monkeypatch.setattr(config, "RETRY_DELAY", 0)
    monkeypatch.setattr(config, "PAUSE_BETWEEN_PRODUCTS", 0)


@pytest.fixture
def fake_store():
    """Make a client whose 'internet' is a dict of url -> (status, html or redirect target).

    A value can also be a function returning (status, body), for pages that
    change between visits. Returns the client and the list of requested urls.
    """

    def make(pages):
        requests = []

        def handle(request):
            url = str(request.url)
            requests.append(url)
            answer = pages[url]
            status, body = answer() if callable(answer) else answer
            if 300 <= status < 400:
                return httpx.Response(status, headers={"Location": body})
            return httpx.Response(status, text=body)

        client = httpx.Client(transport=httpx.MockTransport(handle), follow_redirects=True)
        return client, requests

    return make
