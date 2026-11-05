"""Reading local settings, like DATABASE_URL, from the project's .env file.

    # Lines starting with # are skipped, and so are blank ones.
    DATABASE_URL=postgresql+psycopg://price_tracker:password@localhost:5432/price_tracker

Every way the app runs (the command line, the daily check, `serve`) reads the
same file, so they all use the same database without setting environment
variables by hand. A variable that's already set wins over the file, so a
server can set its own. The file holds passwords: it's in .gitignore.
"""

import os
from pathlib import Path

from . import config


def read(path: Path) -> dict[str, str]:
    """The NAME=value settings in the file at `path`; none if there's no file."""
    try:
        text = path.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        return {}

    values = {}
    for line in text.splitlines():
        name, equals, value = line.partition("=")
        name = name.strip()
        if not equals or not name or name.startswith("#"):
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[name] = value
    return values


def load(path: Path | None = None) -> None:
    """Set the variables in the .env file (config.ENV_FILE) that aren't set already."""
    for name, value in read(config.ENV_FILE if path is None else path).items():
        os.environ.setdefault(name, value)
