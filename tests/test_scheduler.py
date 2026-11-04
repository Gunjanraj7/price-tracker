import xml.etree.ElementTree as ET
from datetime import date, datetime, time
from pathlib import Path

import pytest

from price_tracker import scheduler
from price_tracker.errors import ScheduleError

NS = {"t": "http://schemas.microsoft.com/windows/2004/02/mit/task"}
MORNING, EVENING = time(9, 0), time(21, 0)


@pytest.mark.parametrize("text, expected", [("9:00", time(9, 0)), ("09:05", time(9, 5)), (" 21:30 ", time(21, 30))])
def test_reads_times(text, expected):
    assert scheduler.parse_time(text) == expected


@pytest.mark.parametrize("text", ["9", "9am", "24:00", "12:60", "9:5"])
def test_rejects_times_that_are_not_times(text):
    with pytest.raises(ValueError, match="is not a time"):
        scheduler.parse_time(text)


def test_describes_times_for_people():
    assert scheduler.describe([EVENING, MORNING]) == "9:00 AM and 9:00 PM"
    assert scheduler.describe([time(12, 30)]) == "12:30 PM"
    assert scheduler.describe([time(6, 0), time(14, 0), time(22, 0)]) == "6:00 AM, 2:00 PM and 10:00 PM"


@pytest.mark.parametrize(
    "now, expected",
    [
        (datetime(2026, 11, 5, 8, 0), datetime(2026, 11, 5, 9, 0)),
        (datetime(2026, 11, 5, 9, 0), datetime(2026, 11, 5, 21, 0)),     # the 9:00 check is running now
        (datetime(2026, 11, 5, 22, 0), datetime(2026, 11, 6, 9, 0)),
    ],
)
def test_next_run(now, expected):
    assert scheduler.next_run([MORNING, EVENING], now) == expected


def test_task_runs_the_check_without_a_window_at_each_time():
    project = Path(r"C:\Users\A & B\price-tracker")
    xml = scheduler.task_xml([EVENING, MORNING], project / r".venv\Scripts\pythonw.exe", project, date(2026, 11, 5))
    task = ET.fromstring(xml.encode("utf-16"))

    starts = [element.text for element in task.findall(".//t:CalendarTrigger/t:StartBoundary", NS)]
    assert starts == ["2026-11-05T09:00:00", "2026-11-05T21:00:00"]
    assert task.findtext(".//t:DaysInterval", namespaces=NS) == "1"
    assert task.findtext(".//t:Exec/t:Command", namespaces=NS) == r"C:\Users\A & B\price-tracker\.venv\Scripts\pythonw.exe"
    assert task.findtext(".//t:Exec/t:Arguments", namespaces=NS) == "-m price_tracker check --log"
    assert task.findtext(".//t:Exec/t:WorkingDirectory", namespaces=NS) == r"C:\Users\A & B\price-tracker"
    assert task.findtext(".//t:LogonType", namespaces=NS) == "InteractiveToken"     # as you, no password
    assert task.findtext(".//t:StartWhenAvailable", namespaces=NS) == "true"        # catch up after the PC was off
    assert task.findtext(".//t:DisallowStartIfOnBatteries", namespaces=NS) == "false"


def test_turn_on_query_and_turn_off(task_scheduler):
    assert scheduler.scheduled_times() is None
    scheduler.turn_on([EVENING, MORNING])
    assert scheduler.scheduled_times() == [MORNING, EVENING]

    scheduler.turn_on([time(8, 30)])    # replaces the task
    assert scheduler.scheduled_times() == [time(8, 30)]
    assert list(task_scheduler.tasks) == ["Price Tracker check"]

    assert scheduler.turn_off() is True
    assert scheduler.scheduled_times() is None
    assert scheduler.turn_off() is False


def test_reports_what_task_scheduler_refused(task_scheduler):
    task_scheduler.refusal = "Access is denied."
    with pytest.raises(ScheduleError, match="^Task Scheduler said: Access is denied.$"):
        scheduler.turn_on([MORNING])


def test_explains_what_to_do_elsewhere_than_windows(monkeypatch):
    monkeypatch.setattr(scheduler, "ON_WINDOWS", False)
    with pytest.raises(ScheduleError, match="cron"):
        scheduler.turn_on([MORNING])
