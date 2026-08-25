"""Tests for app.portfolio.service."""

from __future__ import annotations

import pytest

from app.db import repository as repo
from app.market.cache import PriceCache
from app.portfolio import service
from app.portfolio.service import TradeError


@pytest.fixture
def cache() -> PriceCache:
    return PriceCache()


@pytest.fixture(autouse=True)
def wired(db, cache):
    """Every test in this module gets a fresh DB and a fresh price cache wired in."""
    service.init(cache)
    return cache


# -- get_portfolio -------------------------------------------------------


def test_get_portfolio_empty(db, cache):
    portfolio = service.get_portfolio()
    assert portfolio["cash_balance"] == 10000.0
    assert portfolio["positions"] == []
    assert portfolio["total_value"] == 10000.0


def test_get_portfolio_with_position_uses_cached_price(db, cache):
    repo.upsert_position("AAPL", 10, 185.0)
    cache.update("AAPL", 190.5)

    portfolio = service.get_portfolio()

    assert len(portfolio["positions"]) == 1
    position = portfolio["positions"][0]
    assert position["ticker"] == "AAPL"
    assert position["current_price"] == 190.5
    assert position["market_value"] == pytest.approx(1905.0)
    assert position["unrealized_pnl"] == pytest.approx(55.0)
    assert portfolio["total_value"] == pytest.approx(10000.0 + 1905.0)


def test_get_portfolio_falls_back_to_avg_cost_when_no_price(db, cache):
    repo.upsert_position("AAPL", 10, 185.0)

    portfolio = service.get_portfolio()

    position = portfolio["positions"][0]
    assert position["current_price"] == 185.0
    assert position["unrealized_pnl"] == 0.0


# -- execute_trade: buy ---------------------------------------------------


def test_buy_creates_new_position_and_deducts_cash(db, cache):
    cache.update("AAPL", 190.0)

    result = service.execute_trade("AAPL", "buy", 10)

    assert result["trade"]["ticker"] == "AAPL"
    assert result["trade"]["price"] == 190.0
    assert result["portfolio"]["cash_balance"] == pytest.approx(10000.0 - 1900.0)
    position = repo.get_position("AAPL")
    assert position["quantity"] == 10
    assert position["avg_cost"] == 190.0


def test_buy_more_updates_weighted_average_cost(db, cache):
    cache.update("AAPL", 100.0)
    service.execute_trade("AAPL", "buy", 10)  # avg_cost = 100

    cache.update("AAPL", 200.0)
    service.execute_trade("AAPL", "buy", 10)  # avg_cost = (10*100 + 10*200) / 20 = 150

    position = repo.get_position("AAPL")
    assert position["quantity"] == 20
    assert position["avg_cost"] == pytest.approx(150.0)


def test_buy_records_trade_and_snapshot(db, cache):
    cache.update("AAPL", 190.0)
    service.execute_trade("AAPL", "buy", 10)

    trades = repo.list_trades()
    assert len(trades) == 1
    assert trades[0]["side"] == "buy"

    snapshots = repo.list_snapshots()
    assert len(snapshots) == 1


def test_buy_insufficient_cash_raises(db, cache):
    cache.update("AAPL", 190.0)

    with pytest.raises(TradeError, match="insufficient cash"):
        service.execute_trade("AAPL", "buy", 1000)


def test_buy_unknown_ticker_raises(db, cache):
    with pytest.raises(TradeError, match="unknown ticker"):
        service.execute_trade("ZZZZ", "buy", 1)


# -- execute_trade: sell ---------------------------------------------------


def test_sell_partial_reduces_position_and_adds_cash(db, cache):
    cache.update("AAPL", 190.0)
    service.execute_trade("AAPL", "buy", 10)

    cache.update("AAPL", 200.0)
    result = service.execute_trade("AAPL", "sell", 4)

    position = repo.get_position("AAPL")
    assert position["quantity"] == 6
    assert position["avg_cost"] == 190.0  # unchanged by a sell
    assert result["portfolio"]["cash_balance"] == pytest.approx(10000.0 - 1900.0 + 800.0)


def test_sell_all_deletes_position(db, cache):
    cache.update("AAPL", 190.0)
    service.execute_trade("AAPL", "buy", 10)

    service.execute_trade("AAPL", "sell", 10)

    assert repo.get_position("AAPL") is None


def test_sell_insufficient_shares_raises(db, cache):
    cache.update("AAPL", 190.0)
    service.execute_trade("AAPL", "buy", 5)

    with pytest.raises(TradeError, match="insufficient shares"):
        service.execute_trade("AAPL", "sell", 10)


def test_sell_unheld_ticker_raises(db, cache):
    cache.update("AAPL", 190.0)

    with pytest.raises(TradeError, match="insufficient shares"):
        service.execute_trade("AAPL", "sell", 1)
