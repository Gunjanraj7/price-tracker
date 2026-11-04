from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from price_tracker import db, tracking
from price_tracker.api import create_app
from price_tracker.errors import Blocked, UnsupportedSite

AMAZON = "https://www.amazon.in/dp/B0D3DK779N"
FLIPKART = "https://www.flipkart.com/boat-airdopes-131/p/itma0ea2cce3d648?pid=ACCHDYCG92CUSJFT"


@pytest.fixture
def api(store, tmp_path):
    """The API on a new database in memory, with `store` setting the prices."""
    with TestClient(create_app("sqlite://", web_dir=tmp_path)) as client:
        yield client


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


def test_reads_the_real_store_page(page, fake_store):
    client, _ = fake_store({AMAZON: (200, page("amazon_buy_box.html"))})
    with TestClient(create_app("sqlite://", http_client=client)) as api:
        response = add(api, name="Earbuds")
    assert response.json()["item"]["name"] == "Earbuds"
    assert response.json()["item"]["listings"][0]["last_price"] == 470.5


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


def test_serves_the_built_web_ui(tmp_path):
    (tmp_path / "index.html").write_text("<h1>Price Tracker UI</h1>", encoding="utf-8")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "app.js").write_text("console.log('hi')", encoding="utf-8")
    with TestClient(create_app("sqlite://", web_dir=tmp_path)) as api:
        assert "Price Tracker UI" in api.get("/").text
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
        "/api/items",
        "/api/items/{item_id}",
        "/api/items/{item_id}/listings",
        "/api/items/{item_id}/check",
        "/api/items/{item_id}/history",
        "/api/alerts",
    }
