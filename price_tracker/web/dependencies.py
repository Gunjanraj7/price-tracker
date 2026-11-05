"""What endpoints ask for: a database session, the client that fetches store pages, and who is logged in."""

from collections.abc import Iterator
from typing import Annotated

import httpx
from fastapi import Depends, Request
from sqlalchemy.orm import Session

from .. import auth
from ..errors import NotLoggedIn
from ..models import User


def get_session(request: Request) -> Iterator[Session]:
    """A database session for one request, closed after it."""
    with request.app.state.sessions() as session:
        yield session


def get_http_client(request: Request) -> httpx.Client:
    return request.app.state.http_client


SessionDep = Annotated[Session, Depends(get_session)]
ClientDep = Annotated[httpx.Client, Depends(get_http_client)]


def current_user(request: Request, session: SessionDep) -> User:
    """The user this browser is logged in as. Raises NotLoggedIn (401) when it isn't."""
    user = auth.user_for_token(session, request.cookies.get(auth.COOKIE))
    if user is None:
        raise NotLoggedIn("Please log in.")
    return user


# `dependencies=LOGGED_IN` on a router or an endpoint makes it need a login.
LOGGED_IN = [Depends(current_user)]
