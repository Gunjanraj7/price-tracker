"""The web API, for the React UI and anything else that wants the tracked prices.

Run it with `python -m price_tracker serve`. It also serves the built web UI
(web/dist) at http://127.0.0.1:8000, and http://127.0.0.1:8000/docs lets you
try every endpoint in the browser.

There are no logins yet, so it only listens on this computer unless told
otherwise. Don't put it on the internet like this.

The endpoints are plain `def`s: FastAPI runs each request in a worker thread,
which suits the app's blocking database and store requests.
"""

import logging
from collections.abc import Iterator
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path
from typing import Annotated

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, FastAPI, Query, Request, Response, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import URL
from sqlalchemy.orm import Session, sessionmaker

from . import config, db, notify, tracking
from .errors import AlreadyTracked, Blocked, FetchError, NetworkError, NotFound, NotifyError, ParseError
from .fetch import new_client
from .models import Alert, Item
from .schemas import (
    AlertOut,
    CheckResult,
    Health,
    ItemChanges,
    ItemOut,
    ListingError,
    ListingHistory,
    NewItem,
    NewListing,
    PricePoint,
)
from .tracking import Check

log = logging.getLogger(__name__)

# What each problem is answered with. The most specific class that matches wins.
ERROR_STATUS = {
    NotFound: status.HTTP_404_NOT_FOUND,
    AlreadyTracked: status.HTTP_409_CONFLICT,
    FetchError: status.HTTP_422_UNPROCESSABLE_CONTENT,    # a link we can't use, or a page that doesn't exist
    Blocked: status.HTTP_502_BAD_GATEWAY,                 # the store's problem: try again later
    NetworkError: status.HTTP_502_BAD_GATEWAY,
    ParseError: status.HTTP_502_BAD_GATEWAY,
}


def create_app(
    database_url: str | URL | None = None, http_client: httpx.Client | None = None, web_dir: Path | None = None
) -> FastAPI:
    """The API, on the database at `database_url` (db.database_url() by default).

    `http_client` fetches the store pages; by default it's a new one that looks
    like a browser. Tests give a fake one. The web UI is served from `web_dir`
    (config.WEB_DIR by default) once it's built.
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        engine = db.make_engine(database_url)      # brings the tables up to date
        app.state.sessions = db.session_maker(engine)
        app.state.http_client = http_client or new_client()
        try:
            yield
        finally:
            if http_client is None:
                app.state.http_client.close()
            engine.dispose()

    app = FastAPI(
        title="Price Tracker API",
        version="1.0",
        summary="Track Amazon.in and Flipkart prices and get alerts when they drop.",
        lifespan=lifespan,
    )
    app.include_router(router)
    for error_class, code in ERROR_STATUS.items():
        app.add_exception_handler(error_class, _answer_with(code))
    _serve_ui(app, config.WEB_DIR if web_dir is None else web_dir)
    return app


NOT_BUILT = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Price Tracker</title>
<style>body{font-family:system-ui,sans-serif;max-width:40rem;margin:4rem auto;padding:0 1rem;line-height:1.6}
code{background:rgba(127,127,127,.15);padding:.1em .35em;border-radius:4px}</style></head>
<body><h1>Price Tracker</h1>
<p>The API is running, but the web page isn't built yet. In the project folder, run:</p>
<pre><code>cd web
npm install
npm run build</code></pre>
<p>Then reload this page. You can already try the API at <a href="/docs">/docs</a>.</p>
</body></html>"""


def _serve_ui(app: FastAPI, web_dir: Path) -> None:
    """Serve the built UI at /, after the API's routes, or a page that says how to build it."""
    if (web_dir / "index.html").is_file():
        app.mount("/", StaticFiles(directory=web_dir, html=True), name="ui")
        return

    @app.get("/", include_in_schema=False)
    def ui_not_built() -> HTMLResponse:
        return HTMLResponse(NOT_BUILT)


def _answer_with(code: int):
    async def handler(request: Request, error: Exception) -> JSONResponse:
        return JSONResponse(status_code=code, content={"detail": str(error)})

    return handler


def get_session(request: Request) -> Iterator[Session]:
    with request.app.state.sessions() as session:
        yield session


def get_http_client(request: Request) -> httpx.Client:
    return request.app.state.http_client


SessionDep = Annotated[Session, Depends(get_session)]
ClientDep = Annotated[httpx.Client, Depends(get_http_client)]

router = APIRouter(prefix="/api")


@router.get("/health", tags=["status"])
def health() -> Health:
    """Answers when the API is running."""
    return Health()


@router.get("/items", tags=["items"])
def list_items(session: SessionDep) -> list[ItemOut]:
    """Every tracked item, with its latest price on each store."""
    return [ItemOut.model_validate(item) for item in db.all_items(session)]


@router.post("/items", status_code=status.HTTP_201_CREATED, tags=["items"])
def add_item(
    new: NewItem, session: SessionDep, client: ClientDep, request: Request, background: BackgroundTasks
) -> CheckResult:
    """Start tracking a product, and save its price now. This reads the store page, so it takes a few seconds."""
    result = tracking.track(session, new.link, client, target=new.target_price, name=new.name)
    return _answer(result.listing.item, [result], request, background)


@router.get("/items/{item_id}", tags=["items"])
def get_item(item_id: int, session: SessionDep) -> ItemOut:
    return ItemOut.model_validate(tracking.find_item(session, item_id))


@router.patch("/items/{item_id}", tags=["items"])
def change_item(item_id: int, changes: ItemChanges, session: SessionDep) -> ItemOut:
    """Change an item's target price. Send `"target_price": null` to remove it."""
    item = tracking.find_item(session, item_id)
    if "target_price" in changes.model_fields_set:
        item = tracking.set_target(session, item_id, changes.target_price)
    return ItemOut.model_validate(item)


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["items"])
def delete_item(item_id: int, session: SessionDep) -> Response:
    """Stop tracking an item, and delete its price history and alerts."""
    tracking.untrack(session, item_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/items/{item_id}/listings", status_code=status.HTTP_201_CREATED, tags=["items"])
def add_listing(
    item_id: int,
    new: NewListing,
    session: SessionDep,
    client: ClientDep,
    request: Request,
    background: BackgroundTasks,
) -> CheckResult:
    """Add the same product's page on another store to an item."""
    result = tracking.track(session, new.link, client, item_id=item_id)
    return _answer(result.listing.item, [result], request, background)


@router.post("/items/{item_id}/check", tags=["items"])
def check_item(
    item_id: int, session: SessionDep, client: ClientDep, request: Request, background: BackgroundTasks
) -> CheckResult:
    """Check an item's prices now, on every store, and save them. Takes a few seconds per store."""
    item = tracking.find_item(session, item_id)
    results = list(tracking.check_listings(session, list(item.listings), client))
    return _answer(item, results, request, background)


@router.get("/items/{item_id}/history", tags=["items"])
def price_history(
    item_id: int,
    session: SessionDep,
    days: Annotated[int, Query(ge=1, le=3650, description="how far back to go")] = 30,
) -> list[ListingHistory]:
    """The prices recorded for each of an item's store pages, oldest first, for a chart."""
    item = tracking.find_item(session, item_id)
    since = db.utc_now() - timedelta(days=days)
    return [
        ListingHistory(
            listing_id=listing.id,
            site=listing.site,
            prices=[PricePoint.model_validate(check) for check in db.checks_since(session, listing, since)],
        )
        for listing in item.listings
    ]


@router.get("/alerts", tags=["alerts"])
def recent_alerts(
    session: SessionDep, limit: Annotated[int, Query(ge=1, le=500, description="how many")] = 50
) -> list[AlertOut]:
    """The newest alerts first."""
    return [_alert_out(alert) for alert in db.recent_alerts(session, limit)]


def _answer(item: Item, results: list[Check], request: Request, background: BackgroundTasks) -> CheckResult:
    """The answer to adding or checking an item. New alerts go to Telegram after it's sent."""
    alerts = [message for result in results for message in result.alerts]
    if alerts:
        background.add_task(send_alerts, request.app.state.sessions)
    return CheckResult(
        item=ItemOut.model_validate(item),
        alerts=alerts,
        errors=[
            ListingError(listing_id=result.listing.id, site=result.listing.site, error=result.error)
            for result in results
            if result.error
        ],
    )


def send_alerts(sessions: sessionmaker[Session]) -> None:
    """Send the alerts not sent yet to Telegram, if it's set up."""
    telegram = notify.from_environment()
    if telegram is None:
        return
    with sessions() as session, telegram:
        try:
            notify.send_alerts(session, telegram)
        except NotifyError as error:
            log.warning("Telegram: couldn't send alerts. %s They'll be tried again on the next check.", error)


def _alert_out(alert: Alert) -> AlertOut:
    listing = alert.listing
    return AlertOut(
        id=alert.id,
        item_id=listing.item_id,
        item_name=listing.item.name,
        site=listing.site,
        kind=alert.kind,
        price=alert.price,
        message=alert.message,
        url=listing.url,
        created_at=alert.created_at,
        sent_at=alert.sent_at,
    )


# For `uvicorn price_tracker.api:app`. Nothing is opened until it starts.
app = create_app()
