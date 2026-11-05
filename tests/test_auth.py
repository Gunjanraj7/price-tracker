from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from price_tracker import auth, config
from price_tracker.errors import AccountError, WrongPassword

NOW = datetime(2026, 11, 5, 16, 30, tzinfo=timezone.utc)
PASSWORD = "correct horse battery"


def test_a_password_is_saved_as_a_salted_hash(monkeypatch):
    monkeypatch.setattr(auth, "SCRYPT_COST", 2**14)       # the real setting, which tests normally lower
    saved = auth.hash_password(PASSWORD)
    assert saved.startswith("scrypt$16384$8$5$")
    assert PASSWORD not in saved
    assert auth.hash_password(PASSWORD) != saved           # a new salt every time
    assert auth.password_matches(PASSWORD, saved)
    assert not auth.password_matches("correct horse battery!", saved)


def test_a_hash_keeps_the_settings_it_was_made_with(monkeypatch):
    saved = auth.hash_password(PASSWORD)
    monkeypatch.setattr(auth, "SCRYPT_COST", 2**5)         # settings changed later
    assert auth.password_matches(PASSWORD, saved)


@pytest.mark.parametrize("saved", ["", "plain text", "bcrypt$1$2$3$c2FsdA==$a2V5", "scrypt$16$8$1$!!!$!!!", "scrypt$x$8$1$c2FsdA==$a2V5"])
def test_a_broken_hash_matches_nothing(saved):
    assert not auth.password_matches(PASSWORD, saved)


def test_the_same_password_typed_differently_matches():
    saved = auth.hash_password("café-password")             # é as one character
    assert auth.password_matches("café-password", saved)   # e plus a combining accent


def test_accounts(session):
    user = auth.add_user(session, " Gunjan ", PASSWORD, NOW)
    assert (user.username, user.created_at) == ("gunjan", NOW)
    assert auth.has_users(session)
    assert [user.username for user in auth.all_users(session)] == ["gunjan"]
    assert auth.find_user(session, "GUNJAN") is user
    assert session.scalar(text("SELECT password_hash FROM users")).startswith("scrypt$")

    with pytest.raises(AccountError, match="already an account called gunjan"):
        auth.add_user(session, "GUNJAN", PASSWORD)


@pytest.mark.parametrize("username", ["ab", "a" * 31, "has space", "_starts-badly", "emoji😀", ""])
def test_usernames_that_are_refused(session, username):
    with pytest.raises(AccountError, match="3 to 30 characters"):
        auth.add_user(session, username, PASSWORD)
    assert not auth.has_users(session)


def test_passwords_that_are_refused(session):
    with pytest.raises(AccountError, match="at least 8 characters"):
        auth.add_user(session, "gunjan", "1234567")
    with pytest.raises(AccountError, match="at most 200 characters"):
        auth.add_user(session, "gunjan", "x" * 201)


def test_log_in_and_out(session):
    auth.add_user(session, "gunjan", PASSWORD)
    user, token = auth.log_in(session, "Gunjan", PASSWORD, NOW)
    assert user.username == "gunjan"
    assert auth.user_for_token(session, token, NOW) is user

    # The database keeps only a hash of the token, so it can't be used to log in.
    saved = session.scalar(text("SELECT token_hash FROM login_sessions"))
    assert token not in saved
    assert auth.user_for_token(session, saved, NOW) is None

    auth.log_out(session, token)
    assert auth.user_for_token(session, token, NOW) is None
    auth.log_out(session, token)        # again: nothing happens
    auth.log_out(session, None)


def test_a_wrong_password_or_username_gives_the_same_answer(session):
    auth.add_user(session, "gunjan", PASSWORD)
    with pytest.raises(WrongPassword, match="^Wrong username or password.$"):
        auth.log_in(session, "gunjan", "wrong password")
    with pytest.raises(WrongPassword, match="^Wrong username or password.$"):
        auth.log_in(session, "somebody", PASSWORD)


def test_a_login_lasts_30_days(session):
    auth.add_user(session, "gunjan", PASSWORD)
    _, token = auth.log_in(session, "gunjan", PASSWORD, NOW)
    assert auth.user_for_token(session, token, NOW + timedelta(days=config.LOGIN_DAYS) - timedelta(seconds=1))
    assert auth.user_for_token(session, token, NOW + timedelta(days=config.LOGIN_DAYS)) is None
    assert auth.user_for_token(session, "made-up token", NOW) is None
    assert auth.user_for_token(session, "", NOW) is None


def test_old_logins_are_tidied_away(session):
    auth.add_user(session, "gunjan", PASSWORD)
    auth.log_in(session, "gunjan", PASSWORD, NOW)
    auth.log_in(session, "gunjan", PASSWORD, NOW + timedelta(days=config.LOGIN_DAYS + 1))
    assert session.scalar(text("SELECT COUNT(*) FROM login_sessions")) == 1


def test_a_new_password_logs_out_everywhere(session):
    auth.add_user(session, "gunjan", PASSWORD)
    _, phone = auth.log_in(session, "gunjan", PASSWORD, NOW)
    _, laptop = auth.log_in(session, "gunjan", PASSWORD, NOW)

    auth.change_password(session, "GUNJAN", "a brand new password")
    assert auth.user_for_token(session, phone, NOW) is None
    assert auth.user_for_token(session, laptop, NOW) is None
    with pytest.raises(WrongPassword):
        auth.log_in(session, "gunjan", PASSWORD, NOW)
    assert auth.log_in(session, "gunjan", "a brand new password", NOW)[0].username == "gunjan"

    with pytest.raises(AccountError, match="no account called nobody"):
        auth.change_password(session, "nobody", "a brand new password")
    with pytest.raises(AccountError, match="at least 8"):
        auth.change_password(session, "gunjan", "short")


def test_deleting_an_account_deletes_its_logins(session):
    user = auth.add_user(session, "gunjan", PASSWORD)
    auth.log_in(session, "gunjan", PASSWORD, NOW)
    session.delete(user)
    session.commit()
    assert session.scalar(text("SELECT COUNT(*) FROM login_sessions")) == 0


def test_the_throttle_slows_down_guessing():
    throttle = auth.LoginThrottle(tries=3, minutes=10)
    for second in (0, 1, 2):
        assert throttle.wait_seconds("1.2.3.4", second) == 0
        throttle.failed("1.2.3.4", second)

    assert throttle.wait_seconds("1.2.3.4", 2) == 598        # until the first wrong try is 10 minutes old
    assert throttle.wait_seconds("5.6.7.8", 2) == 0          # other addresses can still try
    assert throttle.wait_seconds("1.2.3.4", 600) == 0        # the first one no longer counts


def test_the_throttle_forgets_addresses_with_nothing_left_to_count():
    throttle = auth.LoginThrottle(tries=3, minutes=10)
    throttle.failed("1.2.3.4", 0)
    assert throttle.wait_seconds("1.2.3.4", 601) == 0
    assert throttle._failures == {}


def test_the_right_password_clears_the_wrong_ones():
    throttle = auth.LoginThrottle(tries=3, minutes=10)
    for second in (0, 1, 2):
        throttle.failed("1.2.3.4", second)
    throttle.succeeded("1.2.3.4")
    assert throttle.wait_seconds("1.2.3.4", 3) == 0
