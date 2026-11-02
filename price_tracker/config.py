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
