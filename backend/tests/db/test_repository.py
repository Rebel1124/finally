"""Tests for app.db.repository functions."""

from __future__ import annotations

from app.db import repository as repo


# -- profile -----------------------------------------------------------------


def test_get_profile_returns_seeded_default(db):
    profile = repo.get_profile()
    assert profile["id"] == "default"
    assert profile["cash_balance"] == 10000.0


def test_update_cash_balance(db):
    repo.update_cash_balance(1234.5)
    assert repo.get_profile()["cash_balance"] == 1234.5


# -- watchlist -----------------------------------------------------------------


def test_list_watchlist_returns_seeded_tickers(db):
    watchlist = repo.list_watchlist()
    assert len(watchlist) == 10
    assert all("ticker" in row and "added_at" in row for row in watchlist)


def test_add_watchlist_ticker_uppercases_and_strips(db):
    repo.add_watchlist_ticker("  pypl  ")
    tickers = {row["ticker"] for row in repo.list_watchlist()}
    assert "PYPL" in tickers


def test_add_watchlist_ticker_duplicate_is_noop(db):
    repo.add_watchlist_ticker("AAPL")  # already seeded
    tickers = [row["ticker"] for row in repo.list_watchlist()]
    assert tickers.count("AAPL") == 1


def test_remove_watchlist_ticker(db):
    repo.remove_watchlist_ticker("AAPL")
    tickers = {row["ticker"] for row in repo.list_watchlist()}
    assert "AAPL" not in tickers
    assert len(repo.list_watchlist()) == 9


def test_remove_watchlist_ticker_missing_is_noop(db):
    repo.remove_watchlist_ticker("NOPE")
    assert len(repo.list_watchlist()) == 10


# -- positions -----------------------------------------------------------------


def test_get_positions_empty_by_default(db):
    assert repo.get_positions() == []


def test_get_position_missing_returns_none(db):
    assert repo.get_position("AAPL") is None


def test_upsert_position_inserts(db):
    repo.upsert_position("AAPL", 10.0, 150.0)
    position = repo.get_position("AAPL")
    assert position["ticker"] == "AAPL"
    assert position["quantity"] == 10.0
    assert position["avg_cost"] == 150.0


def test_upsert_position_overwrites_existing(db):
    repo.upsert_position("AAPL", 10.0, 150.0)
    repo.upsert_position("AAPL", 15.0, 160.0)
    positions = repo.get_positions()
    assert len(positions) == 1
    assert positions[0]["quantity"] == 15.0
    assert positions[0]["avg_cost"] == 160.0


def test_delete_position(db):
    repo.upsert_position("AAPL", 10.0, 150.0)
    repo.delete_position("AAPL")
    assert repo.get_position("AAPL") is None


def test_delete_position_missing_is_noop(db):
    repo.delete_position("NOPE")
    assert repo.get_positions() == []


# -- trades -----------------------------------------------------------------


def test_insert_trade_returns_row(db):
    trade = repo.insert_trade("AAPL", "buy", 10.0, 150.0)
    assert trade["ticker"] == "AAPL"
    assert trade["side"] == "buy"
    assert trade["quantity"] == 10.0
    assert trade["price"] == 150.0
    assert trade["id"]
    assert trade["executed_at"]


def test_list_trades_empty_by_default(db):
    assert repo.list_trades() == []


def test_list_trades_most_recent_first(db):
    repo.insert_trade("AAPL", "buy", 10.0, 150.0)
    repo.insert_trade("GOOGL", "buy", 5.0, 100.0)
    trades = repo.list_trades()
    assert [t["ticker"] for t in trades] == ["GOOGL", "AAPL"]


def test_list_trades_respects_limit(db):
    repo.insert_trade("AAPL", "buy", 10.0, 150.0)
    repo.insert_trade("GOOGL", "buy", 5.0, 100.0)
    trades = repo.list_trades(limit=1)
    assert len(trades) == 1
    assert trades[0]["ticker"] == "GOOGL"


# -- portfolio snapshots -----------------------------------------------------------------


def test_list_snapshots_empty_by_default(db):
    assert repo.list_snapshots() == []


def test_insert_and_list_snapshots_oldest_first(db):
    repo.insert_snapshot(10000.0)
    repo.insert_snapshot(10500.0)
    snapshots = repo.list_snapshots()
    assert [s["total_value"] for s in snapshots] == [10000.0, 10500.0]


# -- chat messages -----------------------------------------------------------------


def test_insert_chat_message_returns_row(db):
    message = repo.insert_chat_message("user", "hello")
    assert message["role"] == "user"
    assert message["content"] == "hello"
    assert message["actions"] is None
    assert message["id"]
    assert message["created_at"]


def test_insert_chat_message_with_actions(db):
    message = repo.insert_chat_message("assistant", "bought AAPL", actions_json='{"trades": []}')
    assert message["actions"] == '{"trades": []}'


def test_list_recent_chat_messages_empty_by_default(db):
    assert repo.list_recent_chat_messages() == []


def test_list_recent_chat_messages_chronological_order(db):
    repo.insert_chat_message("user", "first")
    repo.insert_chat_message("assistant", "second")
    repo.insert_chat_message("user", "third")
    messages = repo.list_recent_chat_messages()
    assert [m["content"] for m in messages] == ["first", "second", "third"]


def test_list_recent_chat_messages_respects_limit_keeping_most_recent(db):
    repo.insert_chat_message("user", "first")
    repo.insert_chat_message("assistant", "second")
    repo.insert_chat_message("user", "third")
    messages = repo.list_recent_chat_messages(limit=2)
    assert [m["content"] for m in messages] == ["second", "third"]
