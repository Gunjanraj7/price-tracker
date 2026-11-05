"""Shared test setup.

All tests are offline: they use the small sample pages in tests/pages,
which copy the structure of real Amazon.in and Flipkart pages (checked
November 2026), cut down to the parts the fetcher reads.

Each test that needs a database gets a new SQLite file. `pytest --postgres`
runs them on PostgreSQL instead, in the database TEST_DATABASE_URL names
(from the environment or .env), which they wipe: its name must end in _test.
"""

import json
import os
import subprocess
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
from sqlalchemy import create_engine, make_url, text

from price_tracker import auth, config, db, envfile, notify, scheduler, tracking
from price_tracker.models import ProductInfo

PAGES = Path(__file__).parent / "pages"
REAL_ENV_FILE = config.ENV_FILE     # before any test replaces it


def pytest_addoption(parser):
    parser.addoption(
        "--postgres",
        action="store_true",
        help="run the database tests on PostgreSQL, in the database TEST_DATABASE_URL names "
        "(from the environment or .env). They wipe it, so its name must end in _test.",
    )


@pytest.fixture(scope="session")
def postgres_url(request) -> str | None:
    """With --postgres, the URL of the PostgreSQL database the tests may wipe."""
    if not request.config.getoption("--postgres"):
        return None
    url = os.environ.get("TEST_DATABASE_URL") or envfile.read(REAL_ENV_FILE).get("TEST_DATABASE_URL")
    if not url:
        pytest.exit("--postgres needs TEST_DATABASE_URL, in the environment or in .env.", returncode=4)
    if not (make_url(url).database or "").endswith("_test"):
        pytest.exit("TEST_DATABASE_URL must name a database ending in _test: the tests wipe it.", returncode=4)
    return url


@pytest.fixture
def database_url(postgres_url, tmp_path) -> str:
    """A new, empty database for one test: a SQLite file, or with --postgres the test database, wiped."""
    if postgres_url is None:
        return f"sqlite:///{(tmp_path / 'test.db').as_posix()}"
    engine = create_engine(postgres_url)
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
    engine.dispose()
    return postgres_url


@pytest.fixture
def session(database_url):
    """A session on a new database, with the tables made."""
    with db.connect(database_url) as session:
        yield session


@pytest.fixture
def page():
    """Load a sample page from tests/pages by file name."""
    return lambda name: (PAGES / name).read_text(encoding="utf-8")


@pytest.fixture
def store(monkeypatch):
    """Set the price each link has now, instead of fetching it.

    store[link] = "999" sets the price, None makes it sold out, and an error
    (like Blocked(...)) is raised. The links are the earbuds' pages below.
    """
    ids = {
        "https://www.amazon.in/dp/B0D3DK779N": ("amazon", "B0D3DK779N"),
        "https://www.flipkart.com/boat-airdopes-131/p/itma0ea2cce3d648?pid=ACCHDYCG92CUSJFT": ("flipkart", "ACCHDYCG92CUSJFT"),
    }
    prices = {}

    def fetch(link, client=None):
        answer = prices[link]
        if isinstance(answer, Exception):
            raise answer
        price = None if answer is None else Decimal(answer)
        return ProductInfo(*ids[link], link, "boAt Airdopes 131", price, "INR", price is not None)

    monkeypatch.setattr(tracking, "fetch_product", fetch)
    return prices


@pytest.fixture(autouse=True)
def no_waiting(monkeypatch):
    """Never sleep between retries in tests, or wait before checking a price again."""
    monkeypatch.setattr(config, "RETRY_DELAY", 0)
    monkeypatch.setattr(config, "PAUSE_BETWEEN_PRODUCTS", 0)
    monkeypatch.setattr(config, "PAUSE_BETWEEN_MESSAGES", 0)
    monkeypatch.setattr(config, "CHECK_AGAIN_AFTER_MINUTES", 0)


@pytest.fixture(autouse=True)
def no_real_database(monkeypatch, tmp_path):
    """Tests never use the real database, from DATABASE_URL, .env or price_tracker.db; each makes its own."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(config, "ENV_FILE", tmp_path / "no.env")
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "price_tracker.db")


@pytest.fixture(autouse=True)
def quick_passwords(monkeypatch):
    """Hash passwords with a tiny scrypt cost, so tests that log in stay fast."""
    monkeypatch.setattr(auth, "SCRYPT_COST", 2**4)


@pytest.fixture(autouse=True)
def no_telegram(monkeypatch):
    """Tests never message the real Telegram, even on a computer where it's set up."""
    monkeypatch.delenv(notify.TOKEN_VARIABLE, raising=False)
    monkeypatch.delenv(notify.CHAT_VARIABLE, raising=False)


@pytest.fixture(autouse=True)
def no_task_scheduler(monkeypatch, tmp_path):
    """Tests never change the real Task Scheduler, and log to a temporary folder."""

    def refuse(args):
        raise AssertionError(f"a test ran the real schtasks {args}; use the task_scheduler fixture")

    monkeypatch.setattr(scheduler, "_run_schtasks", refuse)
    monkeypatch.setattr(config, "LOG_PATH", tmp_path / "logs" / "check.log")


class FakeTaskScheduler:
    """A stand-in for Windows' schtasks tool. `tasks` maps task names to their XML."""

    def __init__(self):
        self.tasks = {}
        self.refusal = None     # set to an error message to make the next /Create fail

    def run(self, args):
        command, name = args[0], args[args.index("/TN") + 1]
        if command == "/Create":
            if self.refusal:
                return subprocess.CompletedProcess(args, 1, b"", f"ERROR: {self.refusal}\r\r\n".encode())
            self.tasks[name] = Path(args[args.index("/XML") + 1]).read_text(encoding="utf-16")
            return subprocess.CompletedProcess(args, 0, b"SUCCESS: The scheduled task was created.\r\r\n", b"")
        if name not in self.tasks:
            return subprocess.CompletedProcess(args, 1, b"", b"ERROR: The system cannot find the file specified.\r\r\n")
        if command == "/Query":
            return subprocess.CompletedProcess(args, 0, self.tasks[name].encode(), b"")
        del self.tasks[name]
        return subprocess.CompletedProcess(args, 0, b"SUCCESS: The scheduled task was deleted.\r\r\n", b"")


@pytest.fixture
def task_scheduler(monkeypatch):
    """Use a fake Task Scheduler, as if on Windows. Returns it, to see the tasks."""
    fake = FakeTaskScheduler()
    monkeypatch.setattr(scheduler, "ON_WINDOWS", True)
    monkeypatch.setattr(scheduler, "_run_schtasks", fake.run)
    return fake


class FakeTelegram:
    """A stand-in for Telegram's Bot API servers."""

    token = "123456:test-token"
    chat_id = "42"

    def __init__(self):
        self.calls = []     # (method, params) of every request
        self.sent = []      # texts of the messages Telegram accepted
        self.updates = []   # what getUpdates returns
        self.replies = []   # answers for the next requests, in order: (status, json dict or text),
                            # an httpx error to raise, or None for the normal answer

    def handle(self, request):
        token, method = request.url.path.removeprefix("/bot").rsplit("/", 1)
        params = json.loads(request.content or b"{}")
        self.calls.append((method, params))

        reply = self.replies.pop(0) if self.replies else None
        if isinstance(reply, Exception):
            raise reply
        if reply:
            status, body = reply
            return httpx.Response(status, json=body) if isinstance(body, dict) else httpx.Response(status, text=body)
        if token != self.token:
            return httpx.Response(401, json={"ok": False, "error_code": 401, "description": "Unauthorized"})
        if method == "getUpdates":
            return httpx.Response(200, json={"ok": True, "result": self.updates})
        self.sent.append(params["text"])
        return httpx.Response(200, json={"ok": True, "result": {"message_id": len(self.sent)}})


@pytest.fixture
def telegram(monkeypatch):
    """Set Telegram up, with a fake server. Returns the server, to see what was sent."""
    server = FakeTelegram()
    monkeypatch.setenv(notify.TOKEN_VARIABLE, server.token)
    monkeypatch.setenv(notify.CHAT_VARIABLE, server.chat_id)
    monkeypatch.setattr(notify, "new_client", lambda: httpx.Client(transport=httpx.MockTransport(server.handle)))
    return server


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
