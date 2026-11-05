from datetime import time, timedelta

import pytest
from fastapi.testclient import TestClient

from price_tracker import auth, config, db, scheduler, tracking
from price_tracker.web import create_app
from price_tracker.errors import Blocked, UnsupportedSite

AMAZON = "https://www.amazon.in/dp/B0D3DK779N"
FLIPKART = "https://www.flipkart.com/boat-airdopes-131/p/itma0ea2cce3d648?pid=ACCHDYCG92CUSJFT"
PASSWORD = "a long password"


@pytest.fixture
def new_api(database_url, tmp_path):
    """The API on a new database, not logged in."""
    with TestClient(create_app(database_url, web_dir=tmp_path)) as client:
        yield client


@pytest.fixture
def api(new_api, store):
    """The API on a new database, logged in, with `store` setting the prices."""
    log_in(new_api)
    return new_api


def make_account(api, username="gunjan", password=PASSWORD):
    with api.app.state.sessions() as session:
        auth.add_user(session, username, password)


def log_in(api, username="gunjan", password=PASSWORD):
    """Make the account, and log `api` in with it."""
    make_account(api, username, password)
    response = api.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text


def add(api, link=AMAZON, **fields):
    return api.post("/api/items", json={"link": link, **fields})


def test_health(api):
    assert api.get("/api/health").json() == {"status": "ok"}


def test_add_an_item_and_list_it(api, store):
    store[AMAZON] = "1299.50"
    response = add(api, target_price=1000)
    assert response.status_code == 201
    body = response.json()
    assert (body["alerts"], body["errors"]) == ([], [])

    item = body["item"]
    assert (item["id"], item["name"], item["target_price"], item["active"]) == (1, "boAt Airdopes 131", 1000, True)
    [listing] = item["listings"]
    assert (listing["site"], listing["url"], listing["last_price"], listing["last_in_stock"]) == (
        "amazon", AMAZON, 1299.5, True,
    )
    assert listing["last_checked_at"].endswith("Z")     # UTC

    assert api.get("/api/items").json() == [item]
    assert api.get("/api/items/1").json() == item


def test_reads_the_real_store_page(page, fake_store, database_url, tmp_path):
    client, _ = fake_store({AMAZON: (200, page("amazon_product.html"))})
    with TestClient(create_app(database_url, http_client=client, web_dir=tmp_path)) as api:
        log_in(api)
        response = add(api, name="Earbuds")
    item = response.json()["item"]
    assert item["name"] == "Earbuds"
    [listing] = item["listings"]
    assert listing["last_price"] == 1899
    assert listing["image_url"] == "https://m.media-amazon.com/images/I/31wu8gbDFYL._SY300_SX300_QL70_ML2_.jpg"


def test_a_product_cannot_be_added_twice(api, store):
    store[AMAZON] = "1299"
    add(api)
    response = add(api)
    assert (response.status_code, response.json()) == (409, {"detail": "This product is already tracked, as item 1."})


@pytest.mark.parametrize(
    "error, code",
    [
        (UnsupportedSite("Only links from amazon.in, flipkart.com are supported, got: example.com"), 422),
        (Blocked("The store refused the request (HTTP 503). Try again in a few minutes."), 502),
    ],
)
def test_store_problems_are_explained(api, store, error, code):
    store[AMAZON] = error
    response = add(api)
    assert (response.status_code, response.json()) == (code, {"detail": str(error)})
    assert api.get("/api/items").json() == []


@pytest.mark.parametrize(
    "fields", [{"target_price": 0}, {"target_price": -5}, {"target_price": 10.555}, {"link": ""}, {"name": ""}]
)
def test_rejects_bad_requests(api, fields):
    assert add(api, **fields).status_code == 422


def test_missing_items_are_404(api):
    answers = [
        api.get("/api/items/5"),
        api.patch("/api/items/5", json={"target_price": 1}),
        api.delete("/api/items/5"),
        api.post("/api/items/5/listings", json={"link": AMAZON}),
        api.post("/api/items/5/check"),
        api.get("/api/items/5/history"),
    ]
    for answer in answers:
        assert (answer.status_code, answer.json()) == (404, {"detail": "There is no item 5."})


def test_change_and_remove_the_target(api, store):
    store[AMAZON] = "1299"
    add(api, target_price=1000)
    assert api.patch("/api/items/1", json={"target_price": 1100.5}).json()["target_price"] == 1100.5
    assert api.patch("/api/items/1", json={}).json()["target_price"] == 1100.5     # nothing sent, nothing changed
    assert api.patch("/api/items/1", json={"target_price": None}).json()["target_price"] is None
    assert api.get("/api/items/1").json()["target_price"] is None


def test_delete_an_item(api, store):
    store[AMAZON] = "1299"
    add(api)
    response = api.delete("/api/items/1")
    assert (response.status_code, response.content) == (204, b"")
    assert api.get("/api/items/1").status_code == 404


def test_add_the_other_stores_page(api, store):
    store[AMAZON], store[FLIPKART] = "1299", "1249"
    add(api)
    response = api.post("/api/items/1/listings", json={"link": FLIPKART})
    assert response.status_code == 201
    assert [listing["site"] for listing in response.json()["item"]["listings"]] == ["amazon", "flipkart"]


def test_check_an_item_now(api, store, telegram):
    store[AMAZON], store[FLIPKART] = "1299", "1249"
    add(api, target_price=1000)
    api.post("/api/items/1/listings", json={"link": FLIPKART})

    store[AMAZON], store[FLIPKART] = "999", Blocked("The store refused the request (HTTP 503).")
    body = api.post("/api/items/1/check").json()

    message = "boAt Airdopes 131 is ₹999 on Amazon, at or below your ₹1,000 target"
    assert body["alerts"] == [message]
    assert body["errors"] == [{"listing_id": 2, "site": "flipkart", "error": "The store refused the request (HTTP 503)."}]
    amazon, flipkart = body["item"]["listings"]
    assert amazon["last_price"] == 999
    assert (flipkart["last_price"], flipkart["last_error"]) == (1249, "The store refused the request (HTTP 503).")
    assert telegram.sent == [f"{message}\n{AMAZON}"]     # sent after the answer


def test_price_history(api, store):
    store[AMAZON] = "1299"
    add(api)
    store[AMAZON] = None
    api.post("/api/items/1/check")
    store[AMAZON] = "1199"
    api.post("/api/items/1/check")
    with api.app.state.sessions() as session:      # and a check from 40 days ago
        tracking.check(session, db.get_item(session, 1).listings[0], None, now=db.utc_now() - timedelta(days=40))

    [history] = api.get("/api/items/1/history").json()
    assert (history["listing_id"], history["site"]) == (1, "amazon")
    assert [(point["price"], point["in_stock"]) for point in history["prices"]] == [(1299, True), (None, False), (1199, True)]
    assert len(api.get("/api/items/1/history?days=60").json()[0]["prices"]) == 4


def test_recent_alerts(api, store):
    store[AMAZON] = "990"
    add(api, target_price=1000)

    [alert] = api.get("/api/alerts").json()
    assert (alert["item_id"], alert["item_name"], alert["site"], alert["url"]) == (1, "boAt Airdopes 131", "amazon", AMAZON)
    assert (alert["kind"], alert["price"]) == ("near_target", 990)
    assert alert["sent_at"] is None      # Telegram isn't set up in tests
    assert api.get("/api/alerts?limit=0").status_code == 422


def test_serves_the_built_web_ui(tmp_path, database_url):
    web = tmp_path / "web"
    (web / "assets").mkdir(parents=True)
    (web / "index.html").write_text("<h1>Price Tracker UI</h1>", encoding="utf-8")
    (web / "assets" / "app.js").write_text("console.log('hi')", encoding="utf-8")
    with TestClient(create_app(database_url, web_dir=web)) as api:
        assert "Price Tracker UI" in api.get("/").text      # the page itself needs no login: it shows the login form
        assert api.get("/assets/app.js").status_code == 200
        assert api.get("/api/health").json() == {"status": "ok"}      # the API still comes first
        assert api.get("/docs").status_code == 200


def test_says_how_to_build_the_web_ui(api):
    page = api.get("/")
    assert page.status_code == 200
    assert "npm run build" in page.text


def test_the_docs_list_every_endpoint(api):
    paths = api.get("/openapi.json").json()["paths"]
    assert set(paths) == {
        "/api/health",
        "/api/auth/status",
        "/api/auth/login",
        "/api/auth/logout",
        "/api/items",
        "/api/items/{item_id}",
        "/api/items/{item_id}/listings",
        "/api/items/{item_id}/check",
        "/api/items/{item_id}/history",
        "/api/alerts",
        "/api/schedule",
    }


# ---------------------------------------------------------------- logins

def test_everything_but_health_and_logging_in_needs_a_login(new_api):
    assert new_api.get("/api/health").status_code == 200
    assert new_api.get("/api/auth/status").json() == {"logged_in": False, "username": None, "has_accounts": False}
    answers = [
        new_api.get("/api/items"),
        new_api.post("/api/items", json={"link": AMAZON}),
        new_api.get("/api/items/1"),
        new_api.patch("/api/items/1", json={"target_price": 1}),
        new_api.delete("/api/items/1"),
        new_api.post("/api/items/1/listings", json={"link": AMAZON}),
        new_api.post("/api/items/1/check"),
        new_api.get("/api/items/1/history"),
        new_api.get("/api/alerts"),
        new_api.get("/api/schedule"),
    ]
    for answer in answers:
        assert (answer.status_code, answer.json()) == (401, {"detail": "Please log in."})


def test_log_in_and_out(new_api):
    make_account(new_api, "Gunjan")
    assert new_api.get("/api/auth/status").json() == {"logged_in": False, "username": None, "has_accounts": True}

    response = new_api.post("/api/auth/login", json={"username": " GUNJAN ", "password": PASSWORD})
    assert response.json() == {"logged_in": True, "username": "gunjan", "has_accounts": True}
    cookie = response.headers["set-cookie"]
    assert cookie.startswith(f"{auth.COOKIE}=")
    for part in ("HttpOnly", "SameSite=lax", "Path=/", f"Max-Age={30 * 24 * 3600}"):
        assert part in cookie
    assert "Secure" not in cookie        # plain http here; over https the cookie is Secure too
    assert new_api.get("/api/items").json() == []
    assert new_api.get("/api/auth/status").json()["username"] == "gunjan"

    assert new_api.post("/api/auth/logout").status_code == 204
    assert new_api.get("/api/items").status_code == 401
    assert new_api.get("/api/auth/status").json()["logged_in"] is False
    assert new_api.post("/api/auth/logout").status_code == 204     # logging out twice is fine


def test_a_wrong_password_or_username_is_refused_alike(new_api):
    make_account(new_api)
    for details in ({"username": "gunjan", "password": "not the password"}, {"username": "nobody", "password": PASSWORD}):
        response = new_api.post("/api/auth/login", json=details)
        assert (response.status_code, response.json()) == (401, {"detail": "Wrong username or password."})
        assert "set-cookie" not in response.headers


def test_password_guessing_is_slowed_down(new_api):
    make_account(new_api)
    for _ in range(config.LOGIN_TRIES):
        assert new_api.post("/api/auth/login", json={"username": "gunjan", "password": "a guess!"}).status_code == 401

    response = new_api.post("/api/auth/login", json={"username": "gunjan", "password": PASSWORD})   # even the right one
    assert response.status_code == 429
    assert response.json() == {"detail": "Too many wrong passwords. Try again in 15 minutes."}
    assert 890 <= int(response.headers["retry-after"]) <= 900


def test_changes_from_other_websites_are_refused(api, store):
    store[AMAZON] = "1299"
    for headers in ({"Sec-Fetch-Site": "cross-site"}, {"Sec-Fetch-Site": "same-site"}, {"Origin": "https://evil.example"}):
        response = api.post("/api/items", json={"link": AMAZON}, headers=headers)
        assert (response.status_code, response.json()) == (403, {"detail": "Changes from other websites aren't allowed."})
    assert api.get("/api/items", headers={"Sec-Fetch-Site": "cross-site"}).json() == []    # reading changes nothing

    assert api.post("/api/items", json={"link": AMAZON}, headers={"Sec-Fetch-Site": "same-origin"}).status_code == 201
    assert api.post("/api/items/1/check", headers={"Origin": "http://testserver"}).status_code == 200


# ---------------------------------------------------------------- going easy on the stores

def test_check_now_skips_pages_checked_a_moment_ago(api, store, monkeypatch):
    monkeypatch.setattr(config, "CHECK_AGAIN_AFTER_MINUTES", 5)
    store[AMAZON], store[FLIPKART] = "1299", "1249"
    add(api)

    response = api.post("/api/items/1/check")
    assert response.status_code == 429
    assert response.json() == {
        "detail": "Checked less than 5 minutes ago. To go easy on the stores, try again in 5 minutes."
    }
    assert 290 <= int(response.headers["retry-after"]) <= 300

    with api.app.state.sessions() as session, db.transaction(session):     # as if Amazon was checked 10 minutes ago
        db.get_item(session, 1).listings[0].last_checked_at -= timedelta(minutes=10)
    api.post("/api/items/1/listings", json={"link": FLIPKART})                  # Flipkart: checked just now
    store[AMAZON], store[FLIPKART] = "999", "899"
    amazon, flipkart = api.post("/api/items/1/check").json()["item"]["listings"]
    assert (amazon["last_price"], flipkart["last_price"]) == (999, 1249)       # only Amazon was due


# ---------------------------------------------------------------- the dashboard

def test_items_come_with_what_their_price_history_says(api, store):
    store[AMAZON] = "1299"
    add(api)
    for price in ("999", None, "1099"):
        store[AMAZON] = price
        api.post("/api/items/1/check")

    stats = api.get("/api/items/1").json()["listings"][0]["stats"]
    assert (stats["lowest_price"], stats["highest_price"], stats["usual_price"], stats["checks"]) == (999, 1299, 1099, 3)
    assert stats["previous_price"] is None      # it was sold out at the check before the latest
    assert [(point["price"], point["in_stock"]) for point in stats["recent_prices"]] == [
        (1299, True), (999, True), (None, False), (1099, True),
    ]

    store[AMAZON] = "1050"
    api.post("/api/items/1/check")
    [item] = api.get("/api/items").json()
    assert item["listings"][0]["stats"]["previous_price"] == 1099


def test_the_daily_checks(api, task_scheduler):
    assert api.get("/api/schedule").json() == {"available": True, "on": False, "times": [], "next_check": None}
    scheduler.turn_on([time(21, 0), time(9, 0)])
    answer = api.get("/api/schedule").json()
    assert (answer["available"], answer["on"], answer["times"]) == (True, True, ["09:00", "21:00"])
    assert answer["next_check"].endswith("Z")


def test_the_daily_checks_where_there_is_no_task_scheduler(api, monkeypatch):
    monkeypatch.setattr(scheduler, "ON_WINDOWS", False)
    assert api.get("/api/schedule").json() == {"available": False, "on": False, "times": [], "next_check": None}
