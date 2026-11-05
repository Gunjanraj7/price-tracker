"""Putting the web app together.

The endpoints are plain `def`s: FastAPI runs each request in a worker thread,
which suits the app's blocking database and store requests.
"""

from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI
from sqlalchemy import URL

from .. import auth, config, db
from ..fetch import new_client
from .errors import add_error_handlers
from .routes import alerts, items, login, status
from .security import SameOriginOnly
from .ui import serve_ui


def create_app(
    database_url: str | URL | None = None, http_client: httpx.Client | None = None, web_dir: Path | None = None
) -> FastAPI:
    """The web app, on the database at `database_url` (db.database_url() by default).

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
        version="2.0",
        summary="Track Amazon.in and Flipkart prices and get alerts when they drop.",
        lifespan=lifespan,
    )
    app.state.login_throttle = auth.LoginThrottle()
    app.add_middleware(SameOriginOnly)
    for routes in (status, login, items, alerts):
        app.include_router(routes.router)
    add_error_handlers(app)
    serve_ui(app, config.WEB_DIR if web_dir is None else web_dir)    # after the API, so /api comes first
    return app


# For `uvicorn price_tracker.web:app`. Nothing is opened until it starts.
app = create_app()
