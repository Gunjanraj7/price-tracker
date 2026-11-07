<div align="center">

# 🏷️ Price Tracker

**Stop refreshing product pages. Let the prices come to you.**

Paste an Amazon.in or Flipkart link, tell it what you'd like to pay,
and get a Telegram ping when it's actually a good time to buy.

[![Tests](https://github.com/Gunjanraj7/price-tracker/actions/workflows/tests.yml/badge.svg)](https://github.com/Gunjanraj7/price-tracker/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
<br>
![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-API-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)
![TypeScript](https://img.shields.io/badge/TypeScript-strict-3178C6?logo=typescript&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-18-4169E1?logo=postgresql&logoColor=white)

![The Price Tracker dashboard: four summary tiles, a row of hot deals, and product cards with prices and verdicts](docs/screenshots/dashboard.webp)

</div>

## Why bother?

Prices on Indian stores move all the time, and "40% off" is often the
everyday price in a costume. Price Tracker keeps its **own** record of what
each product really sold for, twice a day, so it can tell you when a price is
genuinely low, not just when a banner says so. Track the same product on both
stores and it shows you whichever is cheaper.

## What it does

- 🔗 **Paste and go.** A product link, a short share link, or the whole message
  the store app shares: all fine.
- 📉 **A real price history** for every product, as a chart or a table.
- 🎯 **Your price, your rules.** Set a target and get an alert when the price
  reaches it, or comes within 5% of it.
- 🔥 **Big-drop alerts** when a price falls 30% or more below its usual price
  (the middle price of the last 30 days).
- 📲 **Telegram pings**, so the good news finds you.
- ⏰ **Checks twice a day on its own** once you switch it on (9:00 and 21:00, or your own times).
- 🧾 **A verdict on every price:** 🎯 Target hit · 🏆 Lowest ever · 🔥 W deal ·
  👍 Good price · 😐 Mid price · 📈 Pricey rn.
- 🔐 **A login**, so the dashboard and its data are yours alone.
- 🌙 Dark mode, a layout that works on your phone, and a little confetti
  when a target is hit.

<table>
  <tr>
    <td width="50%"><img src="docs/screenshots/details.webp" alt="An item's details: both stores side by side, the lowest, usual and highest prices, and a 30-day chart with the target line"></td>
    <td width="50%"><img src="docs/screenshots/dark.webp" alt="The item cards in dark mode"></td>
  </tr>
  <tr>
    <td><img src="docs/screenshots/login.webp" alt="The login page"></td>
    <td align="center"><img src="docs/screenshots/phone.webp" alt="The dashboard on a phone" width="260"></td>
  </tr>
</table>

<sub>The screenshots use demo data.</sub>

## How it works

```mermaid
flowchart LR
    you["You paste a link<br/>(or the 9:00 / 21:00 check runs)"] --> fetch["Fetcher reads the<br/>store page politely"]
    fetch --> db[("PostgreSQL<br/>price history")]
    db --> rules{"Alert rules:<br/>near target?<br/>big drop?"}
    rules -- yes --> tg["📲 Telegram"]
    db --> api["FastAPI<br/>(login required)"] --> ui["React dashboard"]
```

| Part | Built with |
|------|-----------|
| Reading store pages | httpx, Beautiful Soup |
| Database | PostgreSQL (or SQLite), SQLAlchemy 2, Alembic migrations |
| API | FastAPI, with cookie logins and scrypt-hashed passwords |
| Dashboard | React 19, TypeScript, Vite; no UI library, the charts are hand-drawn SVG |
| Alerts and scheduling | Telegram Bot API, Windows Task Scheduler (or cron) |
| Tests | pytest (on SQLite and PostgreSQL), Vitest and Testing Library |

## Getting started

You'll need **Python 3.12+**, **Node.js 20+**, and, if you want it,
**PostgreSQL** (without it, the app quietly uses a SQLite file instead).
The commands below are for Windows; on macOS or Linux use `.venv/bin/python`.

**1. Install it**

```
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
cd web
npm install
npm run build
cd ..
```

**2. Pick a database.** For PostgreSQL, create a login and a database for the
app (in `psql` or pgAdmin):

```sql
CREATE ROLE price_tracker LOGIN PASSWORD 'pick-a-long-random-password';
CREATE DATABASE price_tracker OWNER price_tracker;
```

Then copy `.env.example` to `.env` and put that password in it. The app
creates its tables by itself the first time it runs. Skip this step to use
SQLite.

**3. Make your account.** There's no sign-up page on purpose: accounts are
made from the command line, so nobody else can let themselves in.

```
.venv\Scripts\python.exe -m price_tracker user add YOUR-NAME
```

**4. Start it**

```
.venv\Scripts\python.exe -m price_tracker serve
```

Open **http://127.0.0.1:8000**, log in, and paste your first link. 🎉

## Using it

**In the web app**, paste a link in the top bar and press **Track**. Click a
card's name or photo for its details: the full chart, the lowest, usual and
highest prices, your target (with suggestions such as "lowest seen"), and a
box to add the same product's page on the other store. The tiles and the tabs
in the blue strip filter the cards; **Check all** checks every item now.

**On the command line**, everything is there too. Run these with
`.venv\Scripts\python.exe` as above, or activate the virtual environment first:

| Command | What it does |
|---------|--------------|
| `python -m price_tracker "<link>"` | shows a product's price now, without saving it |
| `python -m price_tracker add "<link>" --target 1500` | starts tracking (the target is optional) |
| `python -m price_tracker add "<link>" --to 1` | adds the other store's page to item 1 |
| `python -m price_tracker list` | your items and their latest prices |
| `python -m price_tracker check` | checks everything now and shows any alerts |
| `python -m price_tracker target 1 1200` | changes item 1's target (`off` removes it) |
| `python -m price_tracker remove 1` | stops tracking item 1 |
| `python -m price_tracker user add/password/list` | manages the accounts |

Put links in quotes: they often contain `&`.

## Telegram alerts

1. In Telegram, message **@BotFather**, send `/newbot` and follow the steps.
   It gives you a token.
2. Add it to your `.env` file as `TELEGRAM_BOT_TOKEN=...`
3. Send your new bot any message, then run `python -m price_tracker telegram`.
   It shows your chat's number: add it to `.env` as `TELEGRAM_CHAT_ID=...`
4. Run the same command again. A test message should arrive. 📲

Keep the token secret: anyone who has it controls your bot. If an alert can't
be sent, it's tried again at the next check, for up to 24 hours. The same alert
isn't repeated for 7 days unless the price drops further.

## Checking every day

```
python -m price_tracker schedule on               # every day at 9:00 and 21:00
python -m price_tracker schedule on 8:30 20:30    # or at your own times
python -m price_tracker schedule                  # is it on? when's the next check?
python -m price_tracker schedule off
```

This uses Windows Task Scheduler. It runs quietly in the background while
you're signed in, and if the PC was asleep at check time, it catches up as
soon as it wakes. What each check found goes to `logs/check.log`. On macOS or
Linux, run `python -m price_tracker check --log` from cron, for example
`0 9,21 * * *`.

## Settings

Local settings live in a `.env` file in the project folder (copy
`.env.example`). It holds passwords, so it's in `.gitignore`: never commit it.

| Setting | What it's for |
|---------|---------------|
| `DATABASE_URL` | the database, e.g. `postgresql+psycopg://price_tracker:password@localhost:5432/price_tracker`; without it, SQLite |
| `TEST_DATABASE_URL` | a database the tests may wipe, for `pytest --postgres` (its name must end in `_test`) |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | where alerts go |

Real environment variables win over the file, which is handy on a server.
The finer knobs, such as alert thresholds, how long a login lasts and how
often a page may be re-checked, are plain constants in `price_tracker/config.py`.

## Playing nice with the stores 🤝

Price Tracker reads the same public pages your browser does, and it's
deliberately unhurried about it:

- one store request at a time, at least 3 seconds apart, even when you press
  **Check all**;
- **Check now** skips a page that was checked less than 5 minutes ago (prices
  rarely change that fast);
- a refused request or a CAPTCHA is retried twice, gently, and then left alone
  until the next check.

It's built for personal use: a handful of products, a couple of checks a day.

## Security, briefly

- Passwords are never stored, only scrypt hashes (OWASP's settings), each with
  its own salt.
- A login is a random token in an HttpOnly, SameSite=Lax cookie; the database
  keeps only a SHA-256 hash of it. Logins last 30 days, and changing your
  password logs you out everywhere.
- Five wrong passwords in 15 minutes and that address has to wait.
- The API refuses changes sent from other websites.
- `serve` listens on your own computer only. Before putting it on the
  internet, put it behind HTTPS; the cookie then becomes Secure too.

## For developers

<details>
<summary><b>Project structure</b></summary>

```
price-tracker/
├── price_tracker/          the Python app
│   ├── cli/                the command line: one module per command group
│   ├── web/                the FastAPI app
│   │   ├── routes/         the endpoints, by topic: login, items, alerts, status
│   │   ├── app.py          puts the app together
│   │   └── …               schemas, dependencies, security, errors, serving the UI
│   ├── stores/             one module per store: amazon.py, flipkart.py
│   ├── migrations/         Alembic migrations
│   ├── fetch.py, links.py  reading store pages, politely
│   ├── tracking.py         adding products, checking them, making alerts
│   ├── alerts.py           the alert rules
│   ├── insights.py         what a price history says: lowest, usual, previous…
│   ├── auth.py             accounts, password hashes, logins
│   ├── notify.py           Telegram
│   ├── scheduler.py        the daily checks
│   ├── db.py, models.py    the database and its tables
│   └── config.py           every number you might want to change
├── web/src/                the React dashboard
│   ├── pages/              the login page and the dashboard
│   ├── components/         layout/, dashboard/, items/, common/
│   ├── hooks/              loading the data, Check all, the details drawer
│   ├── lib/                API calls, formatting, deal maths, chart maths, theme
│   └── styles/             one stylesheet per part of the page
├── tests/                  the Python tests, with sample store pages
└── docs/screenshots/
```

</details>

<details>
<summary><b>Running the tests</b></summary>

```
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe -m pytest              # on a new SQLite file per test
.venv\Scripts\python.exe -m pytest --postgres   # the same tests on PostgreSQL
cd web; npm test                                 # the dashboard's tests
```

The tests are offline: sample store pages, a fake Telegram and a fake Task
Scheduler. They never touch your real database, `.env`, bot or scheduled tasks.
GitHub Actions runs all of them on every push, on Python 3.12 and 3.14 and on
both databases ([the workflow](.github/workflows/tests.yml)).
`--postgres` uses `TEST_DATABASE_URL` and wipes that database before each test,
so give it a database of its own:
`CREATE DATABASE price_tracker_test OWNER price_tracker;`

</details>

<details>
<summary><b>Working on the dashboard</b></summary>

Run the API and Vite's dev server side by side; Vite forwards `/api` to the API
and reloads the page as you edit:

```
.venv\Scripts\python.exe -m price_tracker serve --reload   # terminal 1
cd web; npm run dev                                         # terminal 2: http://localhost:5173
```

`npm run build` writes `web/dist`, which `serve` hosts next to the API.

</details>

<details>
<summary><b>The API</b></summary>

Interactive docs: **http://127.0.0.1:8000/docs** (log in on the web app first,
in the same browser). Everything except `health` and `auth/...` needs a login.

| Endpoint | Does |
|----------|------|
| `POST /api/auth/login` · `POST /api/auth/logout` · `GET /api/auth/status` | log in, log out, who's logged in |
| `GET /api/items` | every item, its latest prices, and what its history says |
| `POST /api/items` | start tracking `{"link": "...", "target_price": 1500}` |
| `GET` · `PATCH` · `DELETE /api/items/{id}` | one item; change its target; stop tracking it |
| `POST /api/items/{id}/listings` | add the other store's page |
| `POST /api/items/{id}/check` | check it now (pages checked in the last 5 minutes are skipped) |
| `GET /api/items/{id}/history?days=30` | the price history, for a chart |
| `GET /api/alerts` | the newest alerts |
| `GET /api/schedule` | whether the daily checks are on, and when the next one is |
| `GET /api/health` | `{"status": "ok"}` |

Prices are rupees as JSON numbers; times are ISO 8601 in UTC. Errors look like
`{"detail": "..."}`, with 401 (log in), 403 (sent by another website), 404, 409
(already tracked), 422 (a link that can't be used), 429 with `Retry-After` (too
many tries, or checked a moment ago) and 502 (the store refused, try later).

</details>

<details>
<summary><b>The database</b></summary>

| Table | One row per | Main fields |
|-------|-------------|-------------|
| `items` | thing you track | name, target_price, active |
| `listings` | item page on one store | site, product_id, url, title, image_url, last_price, last_checked_at, last_error |
| `price_history` | successful check | listing_id, price, in_stock, checked_at |
| `alerts` | alert made | listing_id, kind, price, message, created_at, sent_at |
| `users` | account | username, password_hash |
| `login_sessions` | logged-in browser | user_id, token_hash, expires_at |

Prices are stored as whole paise (₹1,299.50 is `129950`), so they stay exact,
and times in UTC. To change a table, edit `models.py`, then let Alembic write
the migration and read it over:

```
.venv\Scripts\alembic.exe revision --autogenerate --rev-id 0004 -m "what changed"
```

The app applies new migrations by itself the next time it opens the database,
and a test fails if the models and migrations ever disagree.

</details>

<details>
<summary><b>Adding a store, or fixing one that changed</b></summary>

**A new store:** write `price_tracker/stores/<store>.py` with the same names as
`amazon.py` (`NAME`, `DOMAIN`, `SHORT_LINK_HOSTS`, `parse_link`, `link_for`,
`parse_page`), add it to `STORES` in `stores/__init__.py`, and add sample pages
and tests.

**When a store changes its page,** the fetcher fails loudly instead of
guessing, and saves the page to `debug/`. Open it, fix the store's module, and
copy the page into `tests/pages/` as a new test.

</details>

## What's next

- [x] Run the tests on every push with GitHub Actions
- [ ] Put it online: a hosted PostgreSQL, HTTPS, and the daily checks on the server
- [ ] Change your password from the web page
- [ ] Separate lists for several people
- [ ] More stores

## License

[MIT](LICENSE): use it, change it, share it; just keep the copyright notice.

---

<sub>Not affiliated with Amazon or Flipkart; their names belong to them. Price Tracker reads public product pages for personal use, a few times a day.</sub>
