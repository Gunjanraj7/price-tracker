"""Checking prices every day with Windows Task Scheduler.

    python -m price_tracker schedule on [TIME ...]   adds the task (default: config.CHECK_TIMES)
    python -m price_tracker schedule off             removes it
    python -m price_tracker schedule                 says whether it's on

The task runs `pythonw.exe -m price_tracker check --log`: pythonw runs it
without opening a window, and --log adds what it prints to logs/check.log.
It runs as you while you're signed in to Windows, so it needs no password and
sees your Telegram settings. A check missed while the PC was off or asleep
runs as soon as the PC is back.
"""

import re
import subprocess
import sys
import tempfile
from datetime import date, datetime, time, timedelta
from pathlib import Path
from xml.sax.saxutils import escape

from . import config
from .errors import ScheduleError

TASK_NAME = "Price Tracker check"
ON_WINDOWS = sys.platform == "win32"


def parse_time(text: str) -> time:
    """Read a time of day like 9:00, 09:00 or 21:30."""
    match = re.fullmatch(r"([01]?\d|2[0-3]):([0-5]\d)", text.strip())
    if not match:
        raise ValueError(f"{text!r} is not a time; write it like 9:00 or 21:30")
    return time(int(match[1]), int(match[2]))


def describe(times: list[time]) -> str:
    """Write times for people: '9:00 AM and 9:00 PM'."""
    words = [moment.strftime("%I:%M %p").lstrip("0") for moment in sorted(times)]
    return words[0] if len(words) == 1 else f"{', '.join(words[:-1])} and {words[-1]}"


def next_run(times: list[time], now: datetime) -> datetime:
    """When the next check is due, after `now` (local time, like the task)."""
    return min(
        candidate
        for day in (now.date(), now.date() + timedelta(days=1))
        for moment in times
        if (candidate := datetime.combine(day, moment)) > now
    )


def task_xml(times: list[time], python: Path, project_dir: Path, start: date) -> str:
    """The task's definition, in Task Scheduler's XML format."""
    triggers = "".join(
        f"""
    <CalendarTrigger>
      <StartBoundary>{start.isoformat()}T{moment:%H:%M}:00</StartBoundary>
      <ScheduleByDay><DaysInterval>1</DaysInterval></ScheduleByDay>
    </CalendarTrigger>"""
        for moment in sorted(times)
    )
    return f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>Checks the prices of tracked products and sends alerts. Added by "python -m price_tracker schedule on"; remove it with "schedule off".</Description>
  </RegistrationInfo>
  <Triggers>{triggers}
  </Triggers>
  <Principals>
    <Principal id="Author">
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <StartWhenAvailable>true</StartWhenAvailable>
    <ExecutionTimeLimit>PT1H</ExecutionTimeLimit>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{escape(str(python))}</Command>
      <Arguments>-m price_tracker check --log</Arguments>
      <WorkingDirectory>{escape(str(project_dir))}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"""


def python_without_window() -> Path:
    """pythonw.exe beside the Python running this (the project's .venv), which opens no window."""
    python = Path(sys.executable)
    pythonw = python.with_name("pythonw.exe")
    return pythonw if pythonw.exists() else python


def turn_on(times: list[time]) -> None:
    """Add the task, or replace it if it's there, to check at `times` every day."""
    xml = task_xml(times, python_without_window(), config.PROJECT_DIR, date.today())
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "task.xml"
        path.write_text(xml, encoding="utf-16")
        _schtasks("/Create", "/TN", TASK_NAME, "/XML", str(path), "/F")


def turn_off() -> bool:
    """Remove the task. Returns False if it wasn't there."""
    if scheduled_times() is None:
        return False
    _schtasks("/Delete", "/TN", TASK_NAME, "/F")
    return True


def scheduled_times() -> list[time] | None:
    """The times the task checks at, or None when there's no task."""
    result = _schtasks("/Query", "/TN", TASK_NAME, "/XML", check=False)
    if result.returncode != 0:
        return None
    found = re.findall(r"<StartBoundary>[^<]*T(\d\d):(\d\d)", _text(result.stdout))
    return sorted({time(int(hour), int(minute)) for hour, minute in found})


def _schtasks(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    """Run Windows' schtasks tool. With `check`, raise ScheduleError if it fails."""
    if not ON_WINDOWS:
        raise ScheduleError(
            "Scheduling uses Windows Task Scheduler. On macOS or Linux, run"
            " `python -m price_tracker check --log` from cron instead, e.g. at 0 9,21 * * *."
        )
    result = _run_schtasks(list(args))
    if check and result.returncode != 0:
        message = _text(result.stderr or result.stdout).strip().removeprefix("ERROR:").strip()
        raise ScheduleError(f"Task Scheduler said: {message or f'error {result.returncode}'}")
    return result


def _run_schtasks(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(["schtasks", *args], capture_output=True)


def _text(output: bytes) -> str:
    """schtasks writes in the console's code page ("oem"), even the XML that says it's UTF-16."""
    try:
        return output.decode("oem", errors="replace")
    except LookupError:     # not on Windows
        return output.decode("utf-8", errors="replace")
