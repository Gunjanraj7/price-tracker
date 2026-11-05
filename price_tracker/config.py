"""Settings you may want to change."""

from pathlib import Path

# How long to wait for a store to answer, in seconds.
REQUEST_TIMEOUT = 20.0

# Blocks and network trouble usually pass, so try again this many times,
# waiting RETRY_DELAY seconds the first time and twice as long each time after.
RETRIES = 2
RETRY_DELAY = 5.0

# Wait between products when checking several, so the stores don't block us.
PAUSE_BETWEEN_PRODUCTS = 3.0

# The project folder, which has the price_tracker package in it.
PROJECT_DIR = Path(__file__).resolve().parent.parent

# Pages the fetcher could not read are saved here, so you can see what changed.
DEBUG_DIR = PROJECT_DIR / "debug"

# Local settings, like DATABASE_URL, as NAME=value lines (see envfile.py and
# .env.example). It holds passwords, so it's in .gitignore.
ENV_FILE = PROJECT_DIR / ".env"

# The database with your tracked products, their price history and alerts,
# when DATABASE_URL isn't set (in .env or the environment).
DB_PATH = PROJECT_DIR / "price_tracker.db"

# The built web UI (`npm run build` in web/), which `serve` shows at its address.
WEB_DIR = PROJECT_DIR / "web" / "dist"

# When `schedule on` checks prices, every day, unless you give other times.
CHECK_TIMES = ("09:00", "21:00")

# What the scheduled checks print goes here. When it grows past LOG_MAX_BYTES
# it's renamed to check.log.old (replacing the older one) and a new log starts.
LOG_PATH = PROJECT_DIR / "logs" / "check.log"
LOG_MAX_BYTES = 1_000_000

# Alert when the price is at or below your target, or at most this many
# percent above it.
NEAR_TARGET_PERCENT = 5

# Alert when the price is this many percent below its usual price: the
# middle price of the checks in the last BIG_DROP_DAYS days.
BIG_DROP_PERCENT = 30
BIG_DROP_DAYS = 30

# Don't repeat an alert for this many days, unless the price falls further.
ALERT_REPEAT_DAYS = 7

# Alerts are sent to Telegram when it's set up (see README). An alert that
# couldn't be sent is tried again on later checks until it's this many hours
# old; after that the price has probably changed, so it's dropped.
SEND_ALERTS_WITHIN_HOURS = 24

# Wait between Telegram messages: it allows about one a second per chat.
PAUSE_BETWEEN_MESSAGES = 1.0

# A "Check now" in the web app skips a store page checked less than this many
# minutes ago, to go easy on the stores: prices rarely change that fast.
CHECK_AGAIN_AFTER_MINUTES = 5

# Logins to the web app last this many days, or until you log out.
LOGIN_DAYS = 30

# After this many wrong passwords from one address within LOGIN_LOCK_MINUTES,
# that address has to wait until the oldest of them is LOGIN_LOCK_MINUTES old.
LOGIN_TRIES = 5
LOGIN_LOCK_MINUTES = 15

# Account rules. Passwords are only stored as a scrypt hash (see auth.py).
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 200
