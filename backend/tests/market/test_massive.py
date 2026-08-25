"""Tests for app.market.massive_client.MassiveDataSource.

The `massive` RESTClient is never called over the network in these tests —
`MassiveDataSource._fetch_snapshots` (a synchronous, easily-mocked seam) is
patched, or `source._client` is set directly to a stand-in object, per the
approach documented in planning/MARKET_DATA_DESIGN.md section 10.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.market.cache import PriceCache
from app.market.massive_client import MassiveDataSource


def make_snapshot(ticker: str, price: float, timestamp_ns: int):
    """A stand-in for massive's TickerSnapshot, shaped like the real SDK.

    sip_timestamp (not `timestamp` — the installed massive SDK's LastTrade
    model has no such attribute) is Unix nanoseconds, matching the raw REST
    payload's `t` field.
    """
    return SimpleNamespace(
        ticker=ticker,
        last_trade=SimpleNamespace(price=price, sip_timestamp=timestamp_ns),
    )


@pytest.fixture
def cache() -> PriceCache:
    return PriceCache()


@pytest.fixture
def source(cache: PriceCache) -> MassiveDataSource:
    return MassiveDataSource(api_key="test-key", price_cache=cache, poll_interval=0.05)


async def test_start_performs_immediate_poll(monkeypatch, cache, source):
    monkeypatch.setattr(
        source,
        "_fetch_snapshots",
        lambda: [make_snapshot("AAPL", 190.5, 1_700_000_000_000_000_000)],
    )
    await source.start(["AAPL"])
    try:
        assert cache.get_price("AAPL") == 190.5
    finally:
        await source.stop()


async def test_start_sets_client_and_task(monkeypatch, source):
    monkeypatch.setattr(source, "_fetch_snapshots", lambda: [])
    await source.start(["AAPL"])
    try:
        assert source._client is not None
        assert source._task is not None
        assert not source._task.done()
    finally:
        await source.stop()


async def test_stop_cancels_task_and_clears_client(monkeypatch, source):
    monkeypatch.setattr(source, "_fetch_snapshots", lambda: [])
    await source.start(["AAPL"])
    await source.stop()
    assert source._task is None
    assert source._client is None


async def test_stop_is_safe_before_start(source):
    await source.stop()  # should not raise


async def test_get_tickers_reflects_started_list(monkeypatch, source):
    monkeypatch.setattr(source, "_fetch_snapshots", lambda: [])
    await source.start(["AAPL", "GOOGL"])
    try:
        assert source.get_tickers() == ["AAPL", "GOOGL"]
    finally:
        await source.stop()


async def test_add_ticker_uppercases_and_strips():
    source = MassiveDataSource(api_key="k", price_cache=PriceCache())
    await source.add_ticker(" tsla ")
    assert source.get_tickers() == ["TSLA"]


async def test_add_ticker_is_noop_if_already_present():
    source = MassiveDataSource(api_key="k", price_cache=PriceCache())
    await source.add_ticker("TSLA")
    await source.add_ticker("TSLA")
    assert source.get_tickers() == ["TSLA"]


async def test_remove_ticker_removes_from_list_and_cache():
    cache = PriceCache()
    cache.update("TSLA", 250.0)
    source = MassiveDataSource(api_key="k", price_cache=cache)
    await source.add_ticker("TSLA")
    await source.remove_ticker(" tsla ")
    assert source.get_tickers() == []
    assert cache.get("TSLA") is None


async def test_poll_once_noop_without_tickers_or_client(cache, source):
    # No start() called yet — no client, no tickers.
    await source._poll_once()
    assert len(cache) == 0


async def test_poll_once_updates_cache_with_converted_timestamp(cache, source):
    source._client = MagicMock()
    source._tickers = ["AAPL"]
    monkeypatch_snapshot = [make_snapshot("AAPL", 190.5, 1_700_000_000_000_000_000)]
    source._fetch_snapshots = lambda: monkeypatch_snapshot

    await source._poll_once()

    update = cache.get("AAPL")
    assert update is not None
    assert update.price == 190.5
    assert update.timestamp == pytest.approx(1_700_000_000.0)


async def test_poll_once_skips_malformed_snapshot_without_crashing(cache, source):
    source._client = MagicMock()
    source._tickers = ["AAPL", "GOOGL"]
    good = make_snapshot("AAPL", 190.5, 1_700_000_000_000_000_000)
    bad = SimpleNamespace(ticker="GOOGL", last_trade=None)  # missing .price -> AttributeError
    source._fetch_snapshots = lambda: [good, bad]

    await source._poll_once()

    assert cache.get_price("AAPL") == 190.5
    assert cache.get("GOOGL") is None


async def test_poll_once_swallows_fetch_exceptions(cache, source):
    source._client = MagicMock()
    source._tickers = ["AAPL"]

    def _raise():
        raise RuntimeError("network error")

    source._fetch_snapshots = _raise

    await source._poll_once()  # should not raise
    assert cache.get("AAPL") is None


async def test_poll_loop_polls_repeatedly(monkeypatch, cache, source):
    call_count = 0

    def _fetch():
        nonlocal call_count
        call_count += 1
        return [make_snapshot("AAPL", 100.0 + call_count, 1_700_000_000_000_000_000)]

    monkeypatch.setattr(source, "_fetch_snapshots", _fetch)
    await source.start(["AAPL"])
    try:
        await asyncio.sleep(0.18)
        assert call_count >= 2
    finally:
        await source.stop()


async def test_poll_once_updates_cache_using_real_sdk_models(cache, source):
    """Exercise real massive.rest.models objects, not a stand-in.

    Guards against attribute-name drift between our parsing code and the
    installed SDK's actual model shape — a hand-built SimpleNamespace/mock
    can't catch a renamed or missing field the way constructing the real
    model class does.
    """
    from massive.rest.models.snapshot import TickerSnapshot

    source._client = MagicMock()
    source._tickers = ["AAPL"]

    real_snapshot = TickerSnapshot.from_dict(
        {"ticker": "AAPL", "lastTrade": {"p": 190.50, "t": 1_700_000_000_000_000_000}}
    )
    source._fetch_snapshots = lambda: [real_snapshot]

    await source._poll_once()

    update = cache.get("AAPL")
    assert update is not None
    assert update.price == 190.50
    assert update.timestamp == pytest.approx(1_700_000_000.0)
