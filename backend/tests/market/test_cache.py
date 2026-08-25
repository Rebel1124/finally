"""Tests for app.market.cache.PriceCache."""

from __future__ import annotations

import time

from app.market.cache import PriceCache


def test_new_cache_is_empty():
    cache = PriceCache()
    assert len(cache) == 0
    assert cache.get_all() == {}
    assert cache.version == 0


def test_update_returns_price_update():
    cache = PriceCache()
    update = cache.update("AAPL", 100.0, timestamp=1.0)
    assert update.ticker == "AAPL"
    assert update.price == 100.0
    assert update.timestamp == 1.0


def test_first_update_sets_previous_price_equal_to_price():
    cache = PriceCache()
    update = cache.update("AAPL", 100.0, timestamp=1.0)
    assert update.previous_price == 100.0
    assert update.direction == "flat"


def test_second_update_computes_previous_price_from_prior_value():
    cache = PriceCache()
    cache.update("AAPL", 100.0, timestamp=1.0)
    update = cache.update("AAPL", 105.0, timestamp=2.0)
    assert update.previous_price == 100.0
    assert update.price == 105.0
    assert update.direction == "up"


def test_update_rounds_price_to_two_decimals():
    cache = PriceCache()
    update = cache.update("AAPL", 100.126, timestamp=1.0)
    assert update.price == 100.13


def test_update_defaults_timestamp_to_now():
    cache = PriceCache()
    before = time.time()
    update = cache.update("AAPL", 100.0)
    after = time.time()
    assert before <= update.timestamp <= after


def test_version_increments_once_per_update():
    cache = PriceCache()
    assert cache.version == 0
    cache.update("AAPL", 100.0)
    assert cache.version == 1
    cache.update("AAPL", 101.0)
    assert cache.version == 2
    cache.update("GOOGL", 50.0)
    assert cache.version == 3


def test_get_unknown_ticker_returns_none():
    cache = PriceCache()
    assert cache.get("NOPE") is None


def test_get_returns_latest_update():
    cache = PriceCache()
    cache.update("AAPL", 100.0)
    update = cache.update("AAPL", 105.0)
    assert cache.get("AAPL") == update


def test_get_price_returns_float_or_none():
    cache = PriceCache()
    assert cache.get_price("AAPL") is None
    cache.update("AAPL", 100.0)
    assert cache.get_price("AAPL") == 100.0


def test_get_all_returns_shallow_copy():
    cache = PriceCache()
    cache.update("AAPL", 100.0)
    snapshot = cache.get_all()
    snapshot["AAPL"] = None  # mutate the copy
    assert cache.get("AAPL") is not None


def test_get_all_contains_all_tickers():
    cache = PriceCache()
    cache.update("AAPL", 100.0)
    cache.update("GOOGL", 50.0)
    all_prices = cache.get_all()
    assert set(all_prices.keys()) == {"AAPL", "GOOGL"}


def test_remove_deletes_ticker():
    cache = PriceCache()
    cache.update("AAPL", 100.0)
    cache.remove("AAPL")
    assert cache.get("AAPL") is None
    assert "AAPL" not in cache
    assert len(cache) == 0


def test_remove_unknown_ticker_is_noop():
    cache = PriceCache()
    cache.remove("NOPE")  # should not raise
    assert len(cache) == 0


def test_contains():
    cache = PriceCache()
    assert "AAPL" not in cache
    cache.update("AAPL", 100.0)
    assert "AAPL" in cache
