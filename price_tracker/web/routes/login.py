"""Logging in and out. These endpoints work without a login, of course."""

import time

from fastapi import APIRouter, Request, Response, status

from ... import auth
from ...errors import TooSoon, WrongPassword
from ..dependencies import SessionDep
from ..errors import wait_text
from ..schemas import LoginDetails, LoginStatus
from ..security import clear_login_cookie, set_login_cookie

router = APIRouter(prefix="/api/auth", tags=["login"])


@router.get("/status")
def login_status(request: Request, session: SessionDep) -> LoginStatus:
    """Who this browser is logged in as, if anyone, and whether there are accounts yet."""
    user = auth.user_for_token(session, request.cookies.get(auth.COOKIE))
    return LoginStatus(
        logged_in=user is not None,
        username=user.username if user else None,
        has_accounts=user is not None or auth.has_users(session),
    )


@router.post("/login")
def log_in(details: LoginDetails, request: Request, response: Response, session: SessionDep) -> LoginStatus:
    """Log in. The answer sets a cookie that keeps this browser logged in for 30 days.

    401 for a wrong username or password. After 5 wrong ones from one address
    in 15 minutes, that address gets 429, with Retry-After, for a while.
    """
    throttle: auth.LoginThrottle = request.app.state.login_throttle
    address = request.client.host if request.client else "unknown"
    wait = throttle.wait_seconds(address, time.monotonic())
    if wait:
        raise TooSoon(f"Too many wrong passwords. Try again in {wait_text(wait)}.", wait)
    try:
        user, token = auth.log_in(session, details.username, details.password)
    except WrongPassword:
        throttle.failed(address, time.monotonic())
        raise
    throttle.succeeded(address)
    set_login_cookie(response, request, token)
    return LoginStatus(logged_in=True, username=user.username, has_accounts=True)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def log_out(request: Request, session: SessionDep) -> Response:
    """Log this browser out."""
    auth.log_out(session, request.cookies.get(auth.COOKIE))
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_login_cookie(response, request)
    return response
