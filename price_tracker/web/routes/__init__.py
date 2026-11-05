"""The API's endpoints, by topic. Each module has a `router` that app.py adds.

    status.py   /api/health (no login), /api/schedule
    login.py    /api/auth/...: log in, log out, who's logged in (no login needed)
    items.py    /api/items...: track, change, check and remove items, and their price history
    alerts.py   /api/alerts
"""
