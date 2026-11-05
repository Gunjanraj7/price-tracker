"""The web app: the API the React UI talks to, and the built UI itself.

Run it with `python -m price_tracker serve` (or `uvicorn price_tracker.web:app`).
http://127.0.0.1:8000/docs lets you try every endpoint in the browser.

Everything under /api needs a login, except /api/health and /api/auth/...:
POST /api/auth/login sets a cookie that keeps the browser logged in (see
auth.py). Make the account first: `python -m price_tracker user add NAME`.

    app.py           create_app() puts the pieces below together
    routes/          the endpoints, by topic: login, items, alerts, status
    schemas.py       the shapes of requests and answers
    dependencies.py  what endpoints ask for: a database session, the store client, the logged-in user
    security.py      the login cookie, and refusing changes that other websites send
    errors.py        how each kind of problem is answered (401, 404, 429...)
    ui.py            serving the built web UI (web/dist)
"""

from .app import app, create_app

__all__ = ["app", "create_app"]
