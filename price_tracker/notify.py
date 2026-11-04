"""Sending alerts to Telegram.

It needs two environment variables (the README shows how to set them):
    TELEGRAM_BOT_TOKEN  the token @BotFather gave you for your bot
    TELEGRAM_CHAT_ID    the chat to send alerts to; `python -m price_tracker telegram`
                        finds yours

The token lets anyone control your bot, so keep it out of the code and out of Git.

    telegram = notify.from_environment()    # None when Telegram isn't set up
    if telegram:
        with telegram:
            notify.send_alerts(conn, telegram)
"""

import os
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timedelta

import httpx

from . import config, db
from .errors import NotifyError

TOKEN_VARIABLE = "TELEGRAM_BOT_TOKEN"
CHAT_VARIABLE = "TELEGRAM_CHAT_ID"
API_URL = "https://api.telegram.org/bot{token}/{method}"


@dataclass
class Chat:
    """A chat that messaged the bot."""

    id: int
    name: str   # the person's name, or the group's title


class Telegram:
    """A Telegram bot that sends messages to one chat. Use it with `with`, or call close()."""

    def __init__(self, token: str, chat_id: str | None, client: httpx.Client):
        self.token = token
        self.chat_id = chat_id
        self.client = client

    def __enter__(self) -> "Telegram":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    def close(self) -> None:
        self.client.close()

    def send(self, text: str) -> None:
        """Send a message to the chat. Raises NotifyError if Telegram doesn't take it."""
        if not self.chat_id:
            raise NotifyError(
                f"{CHAT_VARIABLE} isn't set. Run `python -m price_tracker telegram` to find your chat ID."
            )
        self._call("sendMessage", chat_id=self.chat_id, text=text, link_preview_options={"is_disabled": True})

    def chats(self) -> list[Chat]:
        """The chats that messaged the bot in the last 24 hours; Telegram forgets older ones."""
        found = {}
        for update in self._call("getUpdates"):
            for kind in ("message", "edited_message", "channel_post", "my_chat_member"):
                chat = (update.get(kind) or {}).get("chat")
                if chat and chat["id"] not in found:
                    person = " ".join(filter(None, (chat.get("first_name"), chat.get("last_name"))))
                    found[chat["id"]] = Chat(chat["id"], chat.get("title") or person or chat.get("username") or "?")
        return list(found.values())

    def _call(self, method: str, **params) -> object:
        """Call a Bot API method and return its result."""
        try:
            response = self.client.post(API_URL.format(token=self.token, method=method), json=params)
        except httpx.HTTPError as error:
            # `from None`: httpx errors can carry the URL, and the URL has the token in it.
            raise NotifyError(f"Could not reach Telegram: {self._hide_token(str(error))}") from None

        try:
            answer = response.json()
        except ValueError:
            answer = None
        if not isinstance(answer, dict):
            answer = {}
        if response.status_code == 200 and answer.get("ok"):
            return answer["result"]
        raise NotifyError(self._explain(response.status_code, answer))

    def _explain(self, status: int, answer: dict) -> str:
        """Say why Telegram refused a request, and what to do about it."""
        description = answer.get("description") or ""
        if status in (401, 404):
            return f"Telegram doesn't accept the bot token. Check {TOKEN_VARIABLE}: it should be the token @BotFather gave you."
        if status == 400 and "chat not found" in description.lower():
            return (
                f"Telegram can't find chat {self.chat_id}. Check {CHAT_VARIABLE};"
                " `python -m price_tracker telegram` shows the right one."
            )
        if status == 403:
            return "The bot isn't allowed to message this chat. Open the bot in Telegram, press Start, and make sure it isn't blocked."
        if status == 429:
            wait = (answer.get("parameters") or {}).get("retry_after")
            return f"Telegram asks to slow down{f'; try again in {wait} seconds' if wait else ''}."
        if status >= 500:
            return f"Telegram had a problem of its own (HTTP {status})."
        return f"Telegram refused the request (HTTP {status}): {self._hide_token(description) or 'no reason given'}"

    def _hide_token(self, text: str) -> str:
        return text.replace(self.token, "<token>")


def new_client() -> httpx.Client:
    return httpx.Client(timeout=config.REQUEST_TIMEOUT)


def from_environment() -> Telegram | None:
    """The bot set up in the environment variables, or None when TELEGRAM_BOT_TOKEN isn't set."""
    token = os.environ.get(TOKEN_VARIABLE, "").strip()
    if not token:
        return None
    chat_id = os.environ.get(CHAT_VARIABLE, "").strip() or None
    return Telegram(token, chat_id, new_client())


def send_alerts(conn: sqlite3.Connection, telegram: Telegram, now: datetime | None = None) -> int:
    """Send the alerts that haven't been sent yet, each with its product link, and mark them sent.

    Returns how many were sent. Alerts older than config.SEND_ALERTS_WITHIN_HOURS
    are skipped, since the price has probably changed. Stops at the first
    failure and raises NotifyError; the rest are tried again next time.
    """
    now = now or db.utc_now()
    pending = db.unsent_alerts(conn, now - timedelta(hours=config.SEND_ALERTS_WITHIN_HOURS))
    for number, alert in enumerate(pending):
        if number:
            time.sleep(config.PAUSE_BETWEEN_MESSAGES)
        telegram.send(f"{alert.message}\n{alert.url}")
        with conn:
            db.mark_sent(conn, alert.id, now)
    return len(pending)
