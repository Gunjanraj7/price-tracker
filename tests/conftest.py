"""Shared test setup.

All tests are offline: they use the small sample pages in tests/pages,
which copy the structure of real Amazon.in and Flipkart pages (checked
November 2026), cut down to the parts the fetcher reads.
"""

from pathlib import Path

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
