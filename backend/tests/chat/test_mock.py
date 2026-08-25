"""Tests for app.chat.mock regex parsing."""

from __future__ import annotations

from app.chat.mock import get_mock_response


def test_buy_with_shares_of():
    result = get_mock_response("buy 10 shares of AAPL")
    assert result.message == "Mock: buying 10 AAPL."
    assert [t.model_dump() for t in result.trades] == [{"ticker": "AAPL", "side": "buy", "quantity": 10.0}]
    assert result.watchlist_changes == []


def test_buy_without_shares_of():
    result = get_mock_response("buy 5 tsla")
    assert result.trades[0].ticker == "TSLA"
    assert result.trades[0].side == "buy"
    assert result.trades[0].quantity == 5.0


def test_sell():
    result = get_mock_response("sell 3 shares of GOOGL")
    assert result.message == "Mock: selling 3 GOOGL."
    assert [t.model_dump() for t in result.trades] == [{"ticker": "GOOGL", "side": "sell", "quantity": 3.0}]


def test_add_to_watchlist():
    result = get_mock_response("add PYPL to the watchlist")
    assert result.message == "Mock: adding PYPL to watchlist."
    assert [w.model_dump() for w in result.watchlist_changes] == [{"ticker": "PYPL", "action": "add"}]
    assert result.trades == []


def test_remove_from_watchlist():
    result = get_mock_response("remove PYPL from watchlist")
    assert result.message == "Mock: removing PYPL from watchlist."
    assert [w.model_dump() for w in result.watchlist_changes] == [{"ticker": "PYPL", "action": "remove"}]


def test_fallback_echo():
    result = get_mock_response("what's my portfolio doing?")
    assert result.message == "Mock response: what's my portfolio doing?"
    assert result.trades == []
    assert result.watchlist_changes == []
