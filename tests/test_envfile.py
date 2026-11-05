import os

from price_tracker import envfile


def test_reads_names_and_values(tmp_path):
    path = tmp_path / ".env"
    path.write_text(
        "﻿# a comment, even with = in it\n"
        "\n"
        "DATABASE_URL=postgresql+psycopg://me:p%40ss@localhost:5432/prices?sslmode=require\n"
        "  SPACED  =  some value  \n"
        'QUOTED="with quotes"\n'
        "SINGLE='single'\n"
        "EMPTY=\n"
        "not a setting\n",
        encoding="utf-8",
    )
    assert envfile.read(path) == {
        "DATABASE_URL": "postgresql+psycopg://me:p%40ss@localhost:5432/prices?sslmode=require",
        "SPACED": "some value",
        "QUOTED": "with quotes",
        "SINGLE": "single",
        "EMPTY": "",
    }


def test_no_file_means_no_settings(tmp_path):
    assert envfile.read(tmp_path / "missing.env") == {}


def test_variables_already_set_win(tmp_path, monkeypatch):
    path = tmp_path / ".env"
    path.write_text("PRICE_TRACKER_TEST_A=from file\nPRICE_TRACKER_TEST_B=from file\n", encoding="utf-8")
    monkeypatch.setenv("PRICE_TRACKER_TEST_A", "already set")
    monkeypatch.delenv("PRICE_TRACKER_TEST_B", raising=False)

    envfile.load(path)      # monkeypatch takes B away again after the test
    assert os.environ["PRICE_TRACKER_TEST_A"] == "already set"
    assert os.environ["PRICE_TRACKER_TEST_B"] == "from file"
