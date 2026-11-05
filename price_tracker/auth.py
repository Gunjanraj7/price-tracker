"""Accounts and logins for the web app.

    python -m price_tracker user add NAME        makes an account; asks for its password
    python -m price_tracker user password NAME   changes it, and logs the account out everywhere
    python -m price_tracker user list            shows the accounts

Passwords are never saved, only a scrypt hash of each with its own random
salt, so the database can't be used to read them. Logging in gives the browser
a random token in a cookie; the database keeps only the token's SHA-256 hash.
"""

import base64
import binascii
import hashlib
import hmac
import math
import re
import secrets
import threading
import unicodedata
from collections import deque
from datetime import datetime, timedelta

from sqlalchemy import delete, exists, select
from sqlalchemy.orm import Session, joinedload

from . import config, db
from .errors import AccountError, WrongPassword
from .models import LoginSession, User

# The cookie that keeps a browser logged in.
COOKIE = "price_tracker_session"

# scrypt's settings, from OWASP's password storage advice: N=2^14, r=8, p=5
# takes 16 MiB of memory and about a fifth of a second per password, which
# makes guessing slow. A hash keeps the settings it was made with.
SCRYPT_COST = 2**14
SCRYPT_BLOCK_SIZE = 8
SCRYPT_PARALLEL = 5
KEY_BYTES = 32

USERNAME = re.compile(r"[a-z0-9][a-z0-9._-]{2,29}")


# ---------------------------------------------------------------- passwords

def hash_password(password: str) -> str:
    """A hash to save instead of the password: 'scrypt$N$r$p$<salt>$<key>'."""
    salt = secrets.token_bytes(16)
    key = _scrypt(password, salt, SCRYPT_COST, SCRYPT_BLOCK_SIZE, SCRYPT_PARALLEL, KEY_BYTES)
    return "$".join(("scrypt", str(SCRYPT_COST), str(SCRYPT_BLOCK_SIZE), str(SCRYPT_PARALLEL), _b64(salt), _b64(key)))


def password_matches(password: str, saved: str) -> bool:
    """Whether `password` is the one `saved` (from hash_password) was made from."""
    try:
        scheme, cost, block_size, parallel, salt, key = saved.split("$")
        expected = base64.b64decode(key, validate=True)
        if scheme != "scrypt" or not expected:
            return False
        actual = _scrypt(password, base64.b64decode(salt, validate=True), int(cost), int(block_size), int(parallel), len(expected))
    except (ValueError, binascii.Error):
        return False
    return hmac.compare_digest(actual, expected)


def _scrypt(password: str, salt: bytes, cost: int, block_size: int, parallel: int, length: int) -> bytes:
    # The same password typed on different keyboards can be different Unicode; NFKC makes it one.
    secret = unicodedata.normalize("NFKC", password).encode()
    return hashlib.scrypt(secret, salt=salt, n=cost, r=block_size, p=parallel, maxmem=64 * 1024 * 1024, dklen=length)


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


# ---------------------------------------------------------------- accounts

def clean_username(username: str) -> str:
    """The username as it's saved: lowercase. Raises AccountError if it can't be one."""
    name = username.strip().lower()
    if not USERNAME.fullmatch(name):
        raise AccountError(
            "A username is 3 to 30 characters: letters, digits, dots, dashes or underscores, starting with a letter or digit."
        )
    return name


def check_password_rules(password: str) -> None:
    """Raise AccountError if `password` is too short or too long to use."""
    if len(password) < config.MIN_PASSWORD_LENGTH:
        raise AccountError(f"The password needs at least {config.MIN_PASSWORD_LENGTH} characters.")
    if len(password) > config.MAX_PASSWORD_LENGTH:
        raise AccountError(f"The password can have at most {config.MAX_PASSWORD_LENGTH} characters.")


def find_user(session: Session, username: str) -> User | None:
    return session.scalar(select(User).where(User.username == username.strip().lower()))


def all_users(session: Session) -> list[User]:
    return list(session.scalars(select(User).order_by(User.id)))


def has_users(session: Session) -> bool:
    return bool(session.scalar(select(exists().select_from(User))))


def add_user(session: Session, username: str, password: str, now: datetime | None = None) -> User:
    """Make an account. Raises AccountError if the name is taken or isn't allowed, or the password is too short."""
    name = clean_username(username)
    check_password_rules(password)
    if find_user(session, name):
        raise AccountError(f"There's already an account called {name}.")
    with db.transaction(session):
        user = User(username=name, password_hash=hash_password(password), created_at=now or db.utc_now())
        session.add(user)
    return user


def change_password(session: Session, username: str, password: str) -> User:
    """Give an account a new password, and log it out everywhere."""
    user = find_user(session, username)
    if user is None:
        raise AccountError(f"There's no account called {username.strip().lower()}.")
    check_password_rules(password)
    with db.transaction(session):
        user.password_hash = hash_password(password)
        session.execute(delete(LoginSession).where(LoginSession.user_id == user.id))
    return user


# ---------------------------------------------------------------- logging in

def log_in(session: Session, username: str, password: str, now: datetime | None = None) -> tuple[User, str]:
    """Check a username and password, and start a login.

    Returns the user and the token for the browser's cookie. Raises WrongPassword
    without saying which of the two was wrong.
    """
    now = now or db.utc_now()
    user = find_user(session, username)
    if user is None:
        hash_password(password)     # take as long as a real check, so the time taken doesn't tell which names exist
        raise WrongPassword("Wrong username or password.")
    if not password_matches(password, user.password_hash):
        raise WrongPassword("Wrong username or password.")

    token = secrets.token_urlsafe(32)
    with db.transaction(session):
        session.execute(delete(LoginSession).where(LoginSession.expires_at <= now))   # tidy up old logins
        session.add(
            LoginSession(
                user=user, token_hash=_digest(token), created_at=now, expires_at=now + timedelta(days=config.LOGIN_DAYS)
            )
        )
    return user, token


def user_for_token(session: Session, token: str | None, now: datetime | None = None) -> User | None:
    """The user a cookie's token is logged in as, or None if it isn't (or the login expired)."""
    if not token:
        return None
    login = session.scalar(
        select(LoginSession).options(joinedload(LoginSession.user)).where(LoginSession.token_hash == _digest(token))
    )
    if login is None or login.expires_at <= (now or db.utc_now()):
        return None
    return login.user


def log_out(session: Session, token: str | None) -> None:
    """End the login with this token, if there is one."""
    if token:
        with db.transaction(session):
            session.execute(delete(LoginSession).where(LoginSession.token_hash == _digest(token)))


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class LoginThrottle:
    """Slows down password guessing.

    After config.LOGIN_TRIES wrong passwords from one address within
    config.LOGIN_LOCK_MINUTES, that address has to wait. It's kept in memory,
    so it starts over when the server restarts. Times are time.monotonic() seconds.
    """

    def __init__(self, tries: int | None = None, minutes: float | None = None):
        self.tries = config.LOGIN_TRIES if tries is None else tries
        self.window = 60 * (config.LOGIN_LOCK_MINUTES if minutes is None else minutes)
        self._failures: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def wait_seconds(self, address: str, now: float) -> int:
        """How many seconds `address` has to wait before trying again: 0 if it may try now."""
        with self._lock:
            failures = self._recent(address, now)
            if len(failures) < self.tries:
                return 0
            return max(1, math.ceil(failures[0] + self.window - now))

    def failed(self, address: str, now: float) -> None:
        with self._lock:
            self._failures[address] = self._recent(address, now)
            self._failures[address].append(now)

    def succeeded(self, address: str) -> None:
        with self._lock:
            self._failures.pop(address, None)

    def _recent(self, address: str, now: float) -> deque[float]:
        """The address's wrong tries still inside the window. Addresses with none are forgotten."""
        failures = self._failures.get(address, deque())
        while failures and failures[0] <= now - self.window:
            failures.popleft()
        if not failures:
            self._failures.pop(address, None)
        return failures
