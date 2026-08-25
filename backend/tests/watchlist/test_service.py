"""Tests for app.watchlist.service."""

from __future__ import annotations

import pytest

from app.db import repository as repo
from app.market.cache import PriceCache
from app.market.simulator import SimulatorDataSource
from app.watchlist import service


@pytest.fixture
def cache() -> PriceCache:
    return PriceCache()


@pytest.fixture
async def source(cache: PriceCache):
    src = SimulatorDataSource(price_cache=cache, update_interval=0.05)
    yield src
    await src.stop()


@pytest.fixture(autouse=True)
def wired(db, cache, source):
    service.init(cache, source)
    return cache


async def test_get_watchlist_returns_seeded_defaults_with_null_prices(db, cache, source):
    watchlist = service.get_watchlist()

    assert len(watchlist) == 10
    tickers = {row["ticker"] for row in watchlist}
    assert "AAPL" in tickers
    assert all(row["price"] is None for row in watchlist)


async def test_get_watchlist_includes_price_once_tracked(db, cache, source):
    await source.start(["AAPL"])

    watchlist = service.get_watchlist()

    aapl = next(row for row in watchlist if row["ticker"] == "AAPL")
    assert aapl["price"] is not None
    assert aapl["direction"] == "flat"


async def test_add_to_watchlist_persists_and_tracks_ticker(db, cache, source):
    await source.start([])

    entry = await service.add_to_watchlist("pypl")

    assert entry["ticker"] == "PYPL"
    assert entry["price"] is not None
    assert any(row["ticker"] == "PYPL" for row in repo.list_watchlist())
    assert "PYPL" in source.get_tickers()


async def test_remove_from_watchlist_deletes_row_and_stops_tracking(db, cache, source):
    await source.start(["AAPL"])

    await service.remove_from_watchlist("AAPL")

    assert all(row["ticker"] != "AAPL" for row in repo.list_watchlist())
    assert "AAPL" not in source.get_tickers()
    assert cache.get("AAPL") is None
