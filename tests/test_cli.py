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
