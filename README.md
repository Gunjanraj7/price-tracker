# Price Tracker

Gets the current price of Amazon.in and Flipkart products from their links,
and tracks prices over time to alert you about drops: in a web app, on the
command line, and on Telegram.

## Setup

You need Python 3.12 or newer, and Node.js 20 or newer for the web app.

```
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
cd web
npm install
npm run build
cd ..
```

## Web app

```
.venv\Scripts\python.exe -m price_tracker serve
```

Then open **http://127.0.0.1:8000**. Paste a product link to start tracking it,
set the price you'd like to pay, check prices now, see each item's price
history as a chart or a table, and read your recent alerts. It follows your
system's light or dark theme and works on a phone-sized screen.

The page is built from `web/` (React, TypeScript and Vite) into `web/dist`, which
`serve` hosts next to the API. Run `npm run build` again after changing it.
While working on the UI, run the API and the Vite dev server side by side;
Vite passes `/api` on to the API and reloads the page as you edit:

```
.venv\Scripts\python.exe -m price_tracker serve --reload    # terminal 1
cd web; npm run dev                                          # terminal 2, then open http://localhost:5173
```

`npm test` in `web/` runs the UI's tests.

## Command line

From the project folder:

```
.venv\Scripts\python.exe -m price_tracker                        # paste links one at a time
.venv\Scripts\python.exe -m price_tracker "<link>" "<link>" ...  # or give them up front
```

A link can be a product link, a share link (`amzn.in/d/…`, `dl.flipkart.com/s/…`)
or the whole message the store app shares. Put links in quotes: they often contain `&`.

## Track prices

```
.venv\Scripts\python.exe -m price_tracker add "<link>" --target 1500   # start tracking (the target is optional)
.venv\Scripts\python.exe -m price_tracker add "<link>" --to 1          # add the other store's page to item 1
.venv\Scripts\python.exe -m price_tracker list                         # tracked items and their latest prices
.venv\Scripts\python.exe -m price_tracker check                        # check everything now and show alerts
.venv\Scripts\python.exe -m price_tracker target 1 1200                # change item 1's target ("off" removes it)
.venv\Scripts\python.exe -m price_tracker remove 1                     # stop tracking item 1
```

An **item** is something you want to buy. It can have one **listing** per store,
so the same earbuds on Amazon and Flipkart are one item with two listings.

Every `check` saves the price of each listing and makes an alert when:

- **near target:** the price is at or below the item's target, or at most 5% above it;
- **big drop:** the price is 30% or more below its usual price, meaning the middle
  price of the last 30 days of checks. This uses the prices the tracker recorded,
  not the store's M.R.P. discount.

The same alert isn't repeated for 7 days unless the price falls further. All
these numbers are in `config.py`. To run `check` by itself every day, see
[Daily checks](#daily-checks).

## Telegram alerts

When Telegram is set up, `add` and `check` also send each new alert to your
Telegram, with the product link. Without it, alerts only show in the terminal.

1. In Telegram, message **@BotFather**, send `/newbot` and follow the steps.
   It gives you a token for your bot.
2. Save the token in an environment variable called `TELEGRAM_BOT_TOKEN`.
   On Windows: search the Start menu for *Edit environment variables for your
   account*, click **New...**, enter the name and paste the token.
3. Open your bot in Telegram and send it any message.
4. Open a new terminal (restart VS Code if you use its terminal, so it sees
   the new variable) and run:
   ```
   .venv\Scripts\python.exe -m price_tracker telegram
   ```
   It lists the chats that messaged your bot. Save your chat's number in an
   environment variable called `TELEGRAM_CHAT_ID`, the same way.
5. Open a new terminal again and run the same command. It sends a test message.

The token lets anyone control your bot: keep it in the environment variable,
never in the code or in Git. If an alert can't be sent, `check` says why and
tries it again next time, for up to 24 hours.

To stop the messages, mute the bot in Telegram, or delete the
`TELEGRAM_BOT_TOKEN` variable to turn Telegram alerts off altogether.

## Daily checks

On Windows, this makes Task Scheduler run `check` every day at 9:00 AM and 9:00 PM:

```
.venv\Scripts\python.exe -m price_tracker schedule on               # turn on (9:00 and 21:00)
.venv\Scripts\python.exe -m price_tracker schedule on 8:30 20:30    # or at other times
.venv\Scripts\python.exe -m price_tracker schedule                  # is it on? next and last check
.venv\Scripts\python.exe -m price_tracker schedule off              # turn off
```

- It runs `pythonw.exe -m price_tracker check --log`, so no window opens. What
  each check prints is added to `logs/check.log`; look there if something
  seems wrong.
- It runs as you while you're signed in to Windows (a locked screen is fine),
  so it needs no password and sends Telegram alerts like a check you run yourself.
- Nothing runs while the PC is off or asleep. A missed check runs as soon as
  the PC is back, once, however many were missed.
- It works on battery too. You can also see the task, called *Price Tracker
  check*, in the Task Scheduler app.

On macOS or Linux, run `python -m price_tracker check --log` from cron instead,
for example `0 9,21 * * *`, from the project folder.

## Web API

A [FastAPI](https://fastapi.tiangolo.com/) web API does what the command line
does, for the web app or anything else. `serve` runs it; open
http://127.0.0.1:8000/docs to see every endpoint and try them in the browser.

| Endpoint | Does |
|----------|------|
| `GET /api/items` | tracked items, with their latest price on each store |
| `POST /api/items` | start tracking a link: `{"link": "...", "target_price": 1500, "name": "..."}` (target and name optional) |
| `GET /api/items/{id}` | one item |
| `PATCH /api/items/{id}` | change the target: `{"target_price": 1200}`, or `null` to remove it |
| `DELETE /api/items/{id}` | stop tracking an item and delete its history |
| `POST /api/items/{id}/listings` | add the other store's page: `{"link": "..."}` |
| `POST /api/items/{id}/check` | check the item's prices now |
| `GET /api/items/{id}/history?days=30` | the recorded prices, oldest first, for a chart |
| `GET /api/alerts?limit=50` | the newest alerts |
| `GET /api/health` | `{"status": "ok"}` when it's running |

Prices are rupees as JSON numbers and times are ISO 8601 in UTC. Errors come
back as `{"detail": "..."}`: 404 for an item that doesn't exist, 409 for a
product that's already tracked, 422 for a link or value that can't be used,
and 502 when the store refused or couldn't be read (try again later). Adding
and checking read the store pages, so they take a few seconds. New alerts go
to Telegram as with the command line.

There are no logins yet, so it only listens on this computer (127.0.0.1).
`--port` changes the port, and `--reload` restarts it when the code changes.

## Database

Everything is saved in `price_tracker.db` (SQLite) in the project folder. The
app uses [SQLAlchemy](https://www.sqlalchemy.org/), so it can also run on
PostgreSQL: install a driver (`pip install "psycopg[binary]"`) and set the
`DATABASE_URL` environment variable, e.g.
`postgresql+psycopg://user:password@host/dbname`.

| Table           | One row per                    | Main fields |
|-----------------|--------------------------------|-------------|
| `items`         | thing you track                | name, target_price, active |
| `listings`      | item page on one store         | item_id, site, product_id, url, title, last_price, last_in_stock, last_checked_at, last_error |
| `price_history` | successful check of a listing  | listing_id, price, in_stock, checked_at |
| `alerts`        | alert made                     | listing_id, kind (`near_target`/`big_drop`), price, message, created_at, sent_at |

Prices are stored as whole paise (₹1,299.50 is `129950`) and times in UTC.
`sent_at` is filled in when the alert is sent to Telegram. Open the file
with any SQLite viewer, such as the SQLite Viewer extension for VS Code.

The tables are defined in `models.py`. Whenever the app opens the database it
brings the tables up to date with the [Alembic](https://alembic.sqlalchemy.org/)
migrations in `price_tracker/migrations/`, so a new database is created and an
older one upgraded by itself. `alembic_version` is Alembic's own table.

### Changing the tables

1. Change the model in `models.py`.
2. From the project folder, have Alembic write the migration:
   ```
   .venv\Scripts\alembic.exe revision --autogenerate --rev-id 0002 -m "add users"
   ```
3. Read the new file in `price_tracker/migrations/versions/` and fix what it got
   wrong (it can't tell a renamed column from a new one, for example).
4. Run the tests. `test_migrations_match_the_models` fails if the models and
   migrations don't agree. The app applies the migration the next time it runs.

### From other Python code

```python
from price_tracker import fetch_product

product = fetch_product("https://www.amazon.in/dp/B088FKCD4J")
print(product.title, product.price, product.in_stock)
```

Tracking from code is in `tracking.py`: `track()`, `check_all()`, `set_target()`,
`untrack()`. They take a session from `db.connect()`.

## Tests

```
.venv\Scripts\python.exe -m pytest
```

The tests are offline and use the sample pages in `tests/pages/`, a fake
Telegram server and a fake Task Scheduler. They never message your real bot
or change your scheduled tasks. The web app's tests are in `web/`: `npm test`.

## Layout

```
price_tracker/
    __init__.py      what other code imports: fetch_product, ProductInfo, errors
    __main__.py      makes `python -m price_tracker` work
    cli.py           the command line (commands, printing, asking for links)
    api.py           the web API (FastAPI): endpoints and how errors are answered
    schemas.py       the shapes of the API's requests and answers
    fetch.py         downloads a page, retries, hands it to the right store
    links.py         finds the link in pasted text and works out the store
    models.py        ProductInfo, PageDetails, and the tables: Item, Listing, PriceCheck, Alert
    db.py            opening the database (SQLite or DATABASE_URL) and the queries on it
    migrations/      Alembic migrations that create and upgrade the tables
    tracking.py      adding products, checking them, making alerts
    alerts.py        the alert rules: near target, big drop
    notify.py        sending alerts to Telegram
    scheduler.py     the daily check, with Windows Task Scheduler
    errors.py        FetchError, TrackingError and their subclasses, NotifyError, ScheduleError
    prices.py        reading "₹1,299.00" and writing ₹1,29,999
    config.py        timeouts, retries, pauses, alert limits, check times, file locations
    stores/
        __init__.py  the list of stores
        common.py    helpers every store uses (CAPTCHA check, schema.org data)
        amazon.py    Amazon.in links and pages
        flipkart.py  Flipkart links and pages
tests/
    pages/           sample HTML pages
    test_*.py        one test file per module
web/                 the web app (React + TypeScript, built with Vite)
    src/App.tsx      the page: add form, items, alerts
    src/components/  ItemCard, PriceHistory (the chart), AddItemForm, AlertsPanel, Toast
    src/api.ts       talks to the API
    src/format.ts    rupees (₹1,29,999), "2 hours ago", parsing typed prices
alembic.ini          settings for the `alembic` command, to write new migrations
```

**Adding a store:** write `stores/<store>.py` with the same names as `amazon.py`
(`NAME`, `DOMAIN`, `SHORT_LINK_HOSTS`, `parse_link`, `link_for`, `parse_page`),
add it to `STORES` in `stores/__init__.py`, and add sample pages and tests.

**When a store changes its page:** the fetcher fails instead of guessing, and
saves the page to `debug/`. Open it, fix the store's module, and copy the page
into `tests/pages/` as a new test.
