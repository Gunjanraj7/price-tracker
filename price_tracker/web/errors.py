"""How each kind of problem is answered: {"detail": "..."} with the status code that fits."""

import math

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from ..errors import (
    AlreadyTracked,
    Blocked,
    FetchError,
    NetworkError,
    NotFound,
    NotLoggedIn,
    ParseError,
    TooSoon,
    WrongPassword,
)

# The most specific class that matches wins.
ERROR_STATUS = {
    NotFound: status.HTTP_404_NOT_FOUND,
    AlreadyTracked: status.HTTP_409_CONFLICT,
    FetchError: status.HTTP_422_UNPROCESSABLE_CONTENT,    # a link we can't use, or a page that doesn't exist
    Blocked: status.HTTP_502_BAD_GATEWAY,                 # the store's problem: try again later
    NetworkError: status.HTTP_502_BAD_GATEWAY,
    ParseError: status.HTTP_502_BAD_GATEWAY,
    NotLoggedIn: status.HTTP_401_UNAUTHORIZED,
    WrongPassword: status.HTTP_401_UNAUTHORIZED,
}


def add_error_handlers(app: FastAPI) -> None:
    for error_class, code in ERROR_STATUS.items():
        app.add_exception_handler(error_class, _answer_with(code))
    app.add_exception_handler(TooSoon, _too_soon)


def _answer_with(code: int):
    async def handler(request: Request, error: Exception) -> JSONResponse:
        return JSONResponse(status_code=code, content={"detail": str(error)})

    return handler


async def _too_soon(request: Request, error: TooSoon) -> JSONResponse:
    """429, with Retry-After: how many seconds to wait."""
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={"detail": str(error)},
        headers={"Retry-After": str(error.seconds)},
    )


def wait_text(seconds: int) -> str:
    """How long to wait, for people: '40 seconds', '1 minute', '12 minutes'."""
    if seconds < 60:
        return f"{seconds} second{'s' if seconds != 1 else ''}"
    minutes = math.ceil(seconds / 60)
    return f"{minutes} minute{'s' if minutes != 1 else ''}"
