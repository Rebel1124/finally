"""Integration-style tests for app.market.simulator.SimulatorDataSource."""

from __future__ import annotations

import asyncio

import pytest

from app.market.cache import PriceCache
from app.market.seed_prices import SEED_PRICES
from app.market.simulator import SimulatorDataSource


@pytest.fixture
def cache() -> PriceCache:
    return PriceCache()


@pytest.fixture
async def source(cache: PriceCache):
    src = SimulatorDataSource(price_cache=cache, update_interval=0.05)
    yield src
    await src.stop()


async def test_start_seeds_cache_immediately(cache, source):
    await source.start(["AAPL", "GOOGL"])
    assert cache.get_price("AAPL") == SEED_PRICES["AAPL"]
    assert cache.get_price("GOOGL") == SEED_PRICES["GOOGL"]


async def test_start_creates_background_task(source):
    await source.start(["AAPL"])
    assert source._task is not None
    assert not source._task.done()


async def test_background_loop_updates_cache_over_time(cache, source):
    await source.start(["AAPL"])
    version_after_start = cache.version
    await asyncio.sleep(0.2)
    assert cache.version > version_after_start


async def test_stop_cancels_background_task(source):
    await source.start(["AAPL"])
    await source.stop()
    assert source._task is None


async def test_stop_is_safe_to_call_multiple_times(source):
    await source.start(["AAPL"])
    await source.stop()
    await source.stop()  # should not raise


async def test_stop_before_start_is_safe(source):
    await source.stop()  # should not raise, task was never created


async def test_get_tickers_before_start_returns_empty_list(source):
    assert source.get_tickers() == []


async def test_get_tickers_after_start(source):
    await source.start(["AAPL", "GOOGL"])
    assert source.get_tickers() == ["AAPL", "GOOGL"]


async def test_add_ticker_updates_simulator_and_cache(cache, source):
    await source.start(["AAPL"])
    await source.add_ticker("GOOGL")
    assert "GOOGL" in source.get_tickers()
    assert cache.get_price("GOOGL") == SEED_PRICES["GOOGL"]


async def test_remove_ticker_updates_simulator_and_cache(cache, source):
    await source.start(["AAPL", "GOOGL"])
    await source.remove_ticker("GOOGL")
    assert "GOOGL" not in source.get_tickers()
    assert cache.get("GOOGL") is None


async def test_remove_ticker_before_start_only_clears_cache(cache, source):
    cache.update("GOOGL", 50.0)
    await source.remove_ticker("GOOGL")
    assert cache.get("GOOGL") is None
