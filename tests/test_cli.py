import sys
from datetime import datetime

import pytest

from price_tracker import cli, config

AMAZON = "https://www.amazon.in/dp/B0D3DK779N"


@pytest.fixture
def run(tmp_path, monkeypatch, page, fake_store, capsys):
    """Run the command line on a new database, with the sample Amazon page (₹470.50) as the store."""
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(cli, "new_client", lambda: fake_store({AMAZON: (200, page("amazon_buy_box.html"))})[0])

    def run_cli(*args):
        code = cli.main(list(args))
        return code, capsys.readouterr().out

    return run_cli


def test_add_list_check_change_and_remove(run):
    code, out = run("add", AMAZON, "--target", "₹480")
    assert code == 0
    assert "Tracking as item 1:" in out
    assert "Price:    ₹470.50" in out
    assert "at or below your ₹480 target" in out

    code, out = run("list")
    assert "Item 1:" in out
    assert "target    ₹480" in out
    assert "amazon    ₹470.50" in out

    code, out = run("check")
    assert code == 0
    assert "Checking 1 store page..." in out
    assert "No alerts." in out    # the alert from adding it isn't repeated

    assert run("target", "1", "off") == (0, "Item 1 target: none\n")
    assert run("remove", "1") == (0, "Stopped tracking item 1.\n")
    assert "Nothing tracked yet" in run("list")[1]


def test_reports_a_missing_item(run):
    assert run("remove", "5") == (1, "Error:    There is no item 5.\n")


@pytest.mark.parametrize("price", ["60k", "0", "-5"])
def test_rejects_prices_that_are_not_prices(run, price):
    with pytest.raises(SystemExit):
        run("add", AMAZON, "--target", price)


def test_links_without_a_command_are_not_saved(run, tmp_path):
    code, out = run(AMAZON)
    assert code == 0
    assert "Price:    ₹470.50" in out
    assert not (tmp_path / "test.db").exists()


def test_alerts_are_sent_to_telegram_once(run, telegram):
    code, out = run("add", AMAZON, "--target", "₹480")
    assert code == 0
    assert out.endswith("Telegram: sent 1 alert.\n")
    [message] = telegram.sent
    assert message.endswith(f"is ₹470.50 on Amazon, at or below your ₹480 target\n{AMAZON}")

    code, out = run("check")
    assert code == 0
    assert "Telegram" not in out
    assert len(telegram.sent) == 1


def test_a_telegram_failure_is_reported_and_tried_again(run, telegram):
    telegram.replies = [(401, {"ok": False, "error_code": 401, "description": "Unauthorized"})]
    code, out = run("add", AMAZON, "--target", "₹480")
    assert code == 1
    assert "Tracking as item 1:" in out
    assert "Telegram: couldn't send alerts. Telegram doesn't accept the bot token." in out

    code, out = run("check")
    assert "Telegram: sent 1 alert." in out
    assert len(telegram.sent) == 1


def test_telegram_setup_without_a_token(run, tmp_path):
    code, out = run("telegram")
    assert code == 1
    assert out.startswith("TELEGRAM_BOT_TOKEN isn't set.")
    assert not (tmp_path / "test.db").exists()


def test_telegram_setup_finds_the_chat_id(run, telegram, monkeypatch):
    monkeypatch.delenv("TELEGRAM_CHAT_ID")
    code, out = run("telegram")
    assert (code, out.splitlines()[0]) == (1, "The token works, but no one has messaged the bot in the last 24 hours.")

    telegram.updates = [{"update_id": 1, "message": {"chat": {"id": 42, "first_name": "Asha"}, "text": "hi"}}]
    code, out = run("telegram")
    assert code == 0
    assert "    42    Asha\n" in out
    assert telegram.sent == []


def test_telegram_setup_sends_a_test_message(run, telegram):
    code, out = run("telegram")
    assert (code, out) == (0, "Sent a test message to chat 42. Check Telegram.\n")
    assert telegram.sent == ["Price Tracker is connected. Price drop alerts will arrive here."]


def test_check_with_log_writes_to_the_log_file(run):
    run("add", AMAZON, "--target", "₹480")
    code, out = run("check", "--log")
    assert (code, out) == (0, "")

    log = config.LOG_PATH.read_text(encoding="utf-8")
    assert log.startswith(cli.LOG_START)
    assert "Checking 1 store page..." in log
    assert log.endswith("=== finished: everything worked ===\n\n")


def test_the_daily_check_runs_without_a_terminal(run, monkeypatch):
    """pythonw.exe, which the daily check uses, has no sys.stdout or sys.stderr."""
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    assert cli.main(["check", "--log"]) == 0
    assert "Nothing to check." in config.LOG_PATH.read_text(encoding="utf-8")


def test_a_crash_is_written_to_the_log(run, monkeypatch):
    def crash(conn, client):
        raise RuntimeError("something broke")

    monkeypatch.setattr(cli, "check", crash)
    code, out = run("check", "--log")
    assert (code, out) == (1, "")
    log = config.LOG_PATH.read_text(encoding="utf-8")
    assert "RuntimeError: something broke" in log
    assert "=== finished: something went wrong, see above ===" in log


def test_a_big_log_is_moved_aside(run, monkeypatch):
    monkeypatch.setattr(config, "LOG_MAX_BYTES", 10)
    config.LOG_PATH.parent.mkdir()
    config.LOG_PATH.write_text("older checks\n", encoding="utf-8")

    run("check", "--log")
    assert (config.LOG_PATH.parent / "check.log.old").read_text(encoding="utf-8") == "older checks\n"
    assert config.LOG_PATH.read_text(encoding="utf-8").startswith(cli.LOG_START)


def test_schedule_on_status_and_off(run, task_scheduler):
    assert run("schedule") == (0, "Daily checks are off. Turn them on with: python -m price_tracker schedule on\n")

    code, out = run("schedule", "on")
    assert code == 0
    assert out.startswith("Daily checks are on: every day at 9:00 AM and 9:00 PM.\n")

    code, out = run("schedule")
    assert code == 0
    assert "every day at 9:00 AM and 9:00 PM" in out
    assert "Next check: " in out
    assert "Last check: none yet" in out

    run("check", "--log")
    code, out = run("schedule")
    today = datetime.now(cli.IST).strftime("%d %b %Y")     # the log is in Indian time
    assert f"Last check: {today}" in out and "(everything worked)" in out

    assert run("schedule", "off") == (0, "Daily checks are off.\n")
    assert run("schedule", "off") == (0, "Daily checks were already off.\n")


def test_schedule_on_at_other_times(run, task_scheduler):
    code, out = run("schedule", "on", "8:30", "20:30")
    assert out.startswith("Daily checks are on: every day at 8:30 AM and 8:30 PM.")


def test_schedule_times_only_go_with_on(run, task_scheduler):
    assert run("schedule", "off", "9:00") == (1, "Error:    times only go with on, like: schedule on 9:00 21:00\n")
    with pytest.raises(SystemExit):
        run("schedule", "on", "25:00")


def test_schedule_reports_task_scheduler_errors(run, task_scheduler):
    task_scheduler.refusal = "Access is denied."
    assert run("schedule", "on") == (1, "Error:    Task Scheduler said: Access is denied.\n")


def test_telegram_setup_reports_a_wrong_token(run, telegram, monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "999:wrong")
    code, out = run("telegram")
    assert code == 1
    assert "doesn't accept the bot token" in out
    assert "999:wrong" not in out
