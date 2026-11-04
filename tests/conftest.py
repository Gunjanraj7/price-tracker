"""Shared test setup.

All tests are offline: they use the small sample pages in tests/pages,
which copy the structure of real Amazon.in and Flipkart pages (checked
November 2026), cut down to the parts the fetcher reads.
"""

import json
import subprocess
from pathlib import Path

import httpx
import pytest

from price_tracker import config, notify, scheduler

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
    monkeypatch.setattr(config, "PAUSE_BETWEEN_MESSAGES", 0)


@pytest.fixture(autouse=True)
def no_real_database(monkeypatch):
    """Tests never use a database set in DATABASE_URL; each makes its own."""
    monkeypatch.delenv("DATABASE_URL", raising=False)


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
