"""Accounts for the web app: user add, user password, user list."""

import argparse
import getpass

from .. import auth, config, db
from ..errors import AccountError
from .output import when


def run(args: argparse.Namespace) -> int:
    """Make an account, change its password, or list the accounts."""
    with db.connect() as session:
        try:
            if args.action == "list":
                users = auth.all_users(session)
                if not users:
                    print("No accounts yet. Make one with: python -m price_tracker user add NAME")
                for user in users:
                    print(f"{user.username:<30} made {when(user.created_at)}")
                return 0

            if not args.name:
                print(f"Error:    say which account, like: python -m price_tracker user {args.action} NAME")
                return 1
            # Check the name before asking for a password, so a typo doesn't cost a password.
            if args.action == "add":
                name = auth.clean_username(args.name)
                if auth.find_user(session, name):
                    raise AccountError(f"There's already an account called {name}.")
            elif auth.find_user(session, args.name) is None:
                raise AccountError(f"There's no account called {args.name.strip().lower()}.")

            password = ask_new_password()
            if password is None:
                return 1
            if args.action == "add":
                user = auth.add_user(session, args.name, password)
                print(f"Made the account {user.username}. Log in with it after: python -m price_tracker serve")
            else:
                user = auth.change_password(session, args.name, password)
                print(f"Changed the password of {user.username}, and logged it out everywhere.")
            return 0
        except AccountError as error:
            print(f"Error:    {error}")
            return 1


def ask_new_password() -> str | None:
    """Ask for a new password twice, without showing it. None if the two differ or typing was cancelled."""
    try:
        first = getpass.getpass(f"Password (at least {config.MIN_PASSWORD_LENGTH} characters, nothing shows as you type): ")
        auth.check_password_rules(first)
        second = getpass.getpass("Type it again: ")
    except (EOFError, KeyboardInterrupt):
        print()
        return None
    if first != second:
        print("Error:    the two passwords are different. Nothing was changed.")
        return None
    return first
