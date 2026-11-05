"""The login cookie, and refusing changes that other websites send."""

from datetime import timedelta
from urllib.parse import urlparse

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.datastructures import Headers

from .. import auth, config


def set_login_cookie(response: Response, request: Request, token: str) -> None:
    """Keep this browser logged in for config.LOGIN_DAYS days."""
    response.set_cookie(
        auth.COOKIE,
        token,
        max_age=int(timedelta(days=config.LOGIN_DAYS).total_seconds()),
        path="/",
        httponly=True,      # page scripts can't read it
        samesite="lax",     # browsers leave it off requests other sites make
        secure=_over_https(request),
    )


def clear_login_cookie(response: Response, request: Request) -> None:
    response.delete_cookie(auth.COOKIE, path="/", httponly=True, samesite="lax", secure=_over_https(request))


def _over_https(request: Request) -> bool:
    return request.url.scheme == "https"


class SameOriginOnly:
    """Refuses changes (POST, PATCH, DELETE...) that other websites send.

    The login cookie is SameSite=Lax, so browsers already leave it off most
    requests from other sites; this refuses the rest, by the Sec-Fetch-Site
    header browsers send (or Origin, from older ones). Requests with neither,
    like curl's, don't come from a web page.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if (
            scope["type"] == "http"
            and scope["method"] not in ("GET", "HEAD", "OPTIONS")
            and _from_another_site(Headers(scope=scope))
        ):
            refusal = JSONResponse({"detail": "Changes from other websites aren't allowed."}, status_code=403)
            await refusal(scope, receive, send)
            return
        await self.app(scope, receive, send)


def _from_another_site(headers: Headers) -> bool:
    site = headers.get("sec-fetch-site")
    if site is not None:
        return site not in ("same-origin", "none")     # "none": typed in the address bar, or a bookmark
    origin = headers.get("origin")
    return origin is not None and urlparse(origin).netloc != headers.get("host")
