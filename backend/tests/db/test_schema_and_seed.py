"""Tests for app.db schema creation and default seeding."""

from __future__ import annotations

from app.db import init_db
from app.db.connection import get_connection
from app.db.repository import get_profile, list_watchlist

EXPECTED_TABLES = {
    "users_profile",
    "watchlist",
    "positions",
    "trades",
    "portfolio_snapshots",
    "chat_messages",
}


def test_init_db_creates_all_tables(db_path):
    init_db()
    conn = get_connection()
    try:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    finally:
        conn.close()
    table_names = {row["name"] for row in rows}
    assert EXPECTED_TABLES <= table_names


def test_init_db_creates_db_file_and_parent_dir(tmp_path, monkeypatch):
    from app import config

    nested_path = tmp_path / "nested" / "finally.db"
    monkeypatch.setattr(config, "DB_PATH", nested_path)
    init_db()
    assert nested_path.exists()


def test_init_db_seeds_default_profile(db):
    profile = get_profile()
    assert profile["id"] == "default"
    assert profile["cash_balance"] == 10000.0
    assert profile["created_at"]


def test_init_db_seeds_default_watchlist(db):
    watchlist = list_watchlist()
    tickers = {row["ticker"] for row in watchlist}
    assert tickers == {"AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA", "META", "JPM", "V", "NFLX"}
    assert len(watchlist) == 10


def test_init_db_is_idempotent_does_not_duplicate_or_reset(db):
    from app.db.repository import update_cash_balance

    update_cash_balance(5000.0)
    init_db()  # called again, simulating a second app startup

    profile = get_profile()
    assert profile["cash_balance"] == 5000.0  # not reset back to 10000.0

    watchlist = list_watchlist()
    assert len(watchlist) == 10  # not duplicated
