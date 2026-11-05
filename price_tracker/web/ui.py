"""Serving the built web UI (web/dist) at /, or a page that says how to build it."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

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


def serve_ui(app: FastAPI, web_dir: Path) -> None:
    """Mount the built UI at /. Call it after adding the API's routes, so they come first."""
    if (web_dir / "index.html").is_file():
        app.mount("/", StaticFiles(directory=web_dir, html=True), name="ui")
        return

    @app.get("/", include_in_schema=False)
    def ui_not_built() -> HTMLResponse:
        return HTMLResponse(NOT_BUILT)
