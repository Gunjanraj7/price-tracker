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

# Pages the fetcher could not read are saved here, so you can see what changed.
DEBUG_DIR = Path(__file__).resolve().parent.parent / "debug"

# The database with your tracked products, their price history and alerts.
DB_PATH = Path(__file__).resolve().parent.parent / "price_tracker.db"

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
