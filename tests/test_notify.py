import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import text

from price_tracker import db, notify
from price_tracker.errors import NotifyError
from price_tracker.models import ProductInfo

AMAZON = "https://www.amazon.in/dp/B0D3DK779N"
START = datetime(2026, 11, 4, 3, 30, tzinfo=timezone.utc)
HOUR = timedelta(hours=1)


def make_alerts(session, *moments):
    """Save an alert made at each of `moments`, and return their ids."""
    product = ProductInfo("amazon", "B0D3DK779N", AMAZON, "Earbuds", Decimal("999"), "INR", True)
    with db.transaction(session):
        listing = db.add_listing(session, db.add_item(session, "Earbuds", None, START), product, START)
        return [
            db.add_alert(session, listing, "big_drop", Decimal("999"), f"Earbuds alert {number}", moment).id
            for number, moment in enumerate(moments, 1)
        ]


def unsent(session):
    return list(session.scalars(text("SELECT id FROM alerts WHERE sent_at IS NULL ORDER BY id")))


def test_not_set_up_without_a_token():
    assert notify.from_environment() is None


def test_sends_each_alert_once_with_its_link(session, telegram):
    make_alerts(session, START, START + HOUR)
    with notify.from_environment() as bot:
        assert notify.send_alerts(session, bot, now=START + 2 * HOUR) == 2
        assert notify.send_alerts(session, bot, now=START + 3 * HOUR) == 0

    assert telegram.sent == [f"Earbuds alert 1\n{AMAZON}", f"Earbuds alert 2\n{AMAZON}"]
    assert telegram.calls[0][1]["chat_id"] == "42"
    assert unsent(session) == []


def test_alerts_older_than_a_day_are_not_sent(session, telegram):
    make_alerts(session, START, START + 25 * HOUR)
    with notify.from_environment() as bot:
        assert notify.send_alerts(session, bot, now=START + 26 * HOUR) == 1
    assert telegram.sent == [f"Earbuds alert 2\n{AMAZON}"]


def test_a_failed_send_stops_and_the_rest_wait_for_next_time(session, telegram):
    first, second, third = make_alerts(session, START, START, START)
    telegram.replies = [None, (502, "<html>Bad Gateway</html>")]

    with notify.from_environment() as bot:
        with pytest.raises(NotifyError, match=re.escape("problem of its own (HTTP 502)")):
            notify.send_alerts(session, bot, now=START + HOUR)
        assert unsent(session) == [second, third]

        assert notify.send_alerts(session, bot, now=START + 2 * HOUR) == 2
    assert unsent(session) == []


@pytest.mark.parametrize(
    "reply, explanation",
    [
        ((401, {"ok": False, "error_code": 401, "description": "Unauthorized"}), "doesn't accept the bot token"),
        ((404, {"ok": False, "error_code": 404, "description": "Not Found"}), "doesn't accept the bot token"),
        ((400, {"ok": False, "error_code": 400, "description": "Bad Request: chat not found"}), "can't find chat 42"),
        ((403, {"ok": False, "error_code": 403, "description": "Forbidden: bot was blocked by the user"}), "Press Start"),
        (
            (429, {"ok": False, "error_code": 429, "description": "Too Many Requests", "parameters": {"retry_after": 5}}),
            "try again in 5 seconds",
        ),
        ((400, {"ok": False, "error_code": 400, "description": "Bad Request: message is too long"}), "message is too long"),
    ],
)
def test_explains_what_telegram_refused(telegram, reply, explanation):
    telegram.replies = [reply]
    with notify.from_environment() as bot, pytest.raises(NotifyError, match=re.compile(re.escape(explanation), re.I)):
        bot.send("hello")


def test_errors_never_show_the_token(telegram):
    url = f"https://api.telegram.org/bot{telegram.token}/sendMessage"
    telegram.replies = [httpx.ConnectError(f"Could not connect to {url}")]
    with notify.from_environment() as bot, pytest.raises(NotifyError) as caught:
        bot.send("hello")
    assert str(caught.value) == "Could not reach Telegram: Could not connect to https://api.telegram.org/bot<token>/sendMessage"
    assert caught.value.__cause__ is None and caught.value.__suppress_context__


def test_sending_needs_a_chat_id(telegram, monkeypatch):
    monkeypatch.delenv(notify.CHAT_VARIABLE)
    with notify.from_environment() as bot, pytest.raises(NotifyError, match="TELEGRAM_CHAT_ID isn't set"):
        bot.send("hello")
    assert telegram.calls == []


def test_finds_the_chats_that_messaged_the_bot(telegram):
    private = {"id": 42, "type": "private", "first_name": "Asha", "last_name": "Rao"}
    telegram.updates = [
        {"update_id": 1, "message": {"chat": private, "text": "hi"}},
        {"update_id": 2, "message": {"chat": private, "text": "hello again"}},
        {"update_id": 3, "my_chat_member": {"chat": {"id": -100, "type": "group", "title": "Deals"}}},
        {"update_id": 4, "message": {"chat": {"id": 7, "type": "private", "username": "nameless"}}},
    ]
    with notify.from_environment() as bot:
        assert bot.chats() == [notify.Chat(42, "Asha Rao"), notify.Chat(-100, "Deals"), notify.Chat(7, "nameless")]
