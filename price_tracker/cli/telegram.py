"""Setting up Telegram alerts, step by step: the token, then the chat ID, then a test message."""

import argparse

from .. import notify
from ..errors import NotifyError


def run(args: argparse.Namespace | None = None) -> int:
    telegram = notify.from_environment()
    if telegram is None:
        print(f"{notify.TOKEN_VARIABLE} isn't set. To get alerts on Telegram:")
        print("  1. In Telegram, message @BotFather and send /newbot. It gives you a token.")
        print(f"  2. Put it in the project's .env file as {notify.TOKEN_VARIABLE}=<token>,")
        print("     or in an environment variable of that name (then open a new terminal).")
        print("  3. Send your bot any message, then run this again.")
        return 1

    with telegram:
        try:
            if telegram.chat_id:
                telegram.send("Price Tracker is connected. Price drop alerts will arrive here.")
                print(f"Sent a test message to chat {telegram.chat_id}. Check Telegram.")
                return 0
            chats = telegram.chats()
        except NotifyError as error:
            print(f"Error:    {error}")
            return 1

    if not chats:
        print("The token works, but no one has messaged the bot in the last 24 hours.")
        print("Open your bot in Telegram, send it any message, then run this again.")
        return 1
    print("The token works. These chats messaged your bot:")
    for chat in chats:
        print(f"    {chat.id}    {chat.name}")
    print(f"Put your chat's number in .env as {notify.CHAT_VARIABLE}=<number> (or an environment")
    print("variable of that name), and run this again to send a test message.")
    return 0
