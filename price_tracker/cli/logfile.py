"""--log: what a command prints goes to logs/check.log instead of the screen.

The daily check runs like this, under pythonw.exe, which has no screen to print to.
"""

import traceback
from collections.abc import Callable
from contextlib import redirect_stderr, redirect_stdout

from .. import config, db
from .output import IST

# How each logged run starts and ends in the log file.
LOG_START = "=== check at "
LOG_END = "=== finished: "


def run_logged(command: Callable[[], int]) -> int:
    """Run `command`, adding what it prints (and any crash) to config.LOG_PATH. Returns its exit code."""
    log_path = config.LOG_PATH
    log_path.parent.mkdir(parents=True, exist_ok=True)
    if log_path.exists() and log_path.stat().st_size > config.LOG_MAX_BYTES:
        log_path.replace(log_path.with_name(log_path.name + ".old"))

    with open(log_path, "a", encoding="utf-8") as log, redirect_stdout(log), redirect_stderr(log):
        print(f"{LOG_START}{db.utc_now().astimezone(IST):%d %b %Y, %I:%M %p} ===")
        try:
            code = command()
        except Exception:
            traceback.print_exc()
            code = 1
        print(f"{LOG_END}{'everything worked' if code == 0 else 'something went wrong, see above'} ===\n")
    return code


def last_logged_check() -> str | None:
    """When the last logged check ran and how it went: '05 Nov 2026, 09:00 PM (everything worked)'."""
    try:
        lines = config.LOG_PATH.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return None
    started = result = None
    for line in lines:
        if line.startswith(LOG_START):
            started, result = line.removeprefix(LOG_START).removesuffix(" ==="), "still running, or stopped early"
        elif line.startswith(LOG_END) and started:
            result = line.removeprefix(LOG_END).removesuffix(" ===")
    return f"{started} ({result})" if started else None
