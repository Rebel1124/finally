"""Tests for the SSE price streaming endpoint."""

import json

import pytest

from app.market.cache import PriceCache
from app.market.stream import _generate_events, create_stream_router


class _FakeClient:
    """Stand-in for fastapi.Request.client."""

    def __init__(self, host: str = "127.0.0.1") -> None:
        self.host = host


class _FakeRequest:
    """Minimal stand-in for fastapi.Request — enough for _generate_events.

    Disconnects after `disconnect_after` non-disconnected checks, so a test
    can control exactly how many loop iterations run without real sleeps.
    """

    def __init__(self, disconnect_after: int | None = None) -> None:
        self.client = _FakeClient()
        self._disconnect_after = disconnect_after
        self._checks = 0

    async def is_disconnected(self) -> bool:
        self._checks += 1
        if self._disconnect_after is None:
            return False
        return self._checks > self._disconnect_after


def _data_events(events: list[str]) -> list[dict]:
    """Parse the JSON payload out of every 'data: ...' SSE frame."""
    return [json.loads(e[len("data: ") :].strip()) for e in events if e.startswith("data: ")]


class TestCreateStreamRouter:
    """Tests for the router factory itself."""

    def test_registers_prices_route(self):
        router = create_stream_router(PriceCache())
        paths = [route.path for route in router.routes]
        assert "/api/stream/prices" in paths

    def test_route_is_get_only(self):
        router = create_stream_router(PriceCache())
        route = next(r for r in router.routes if r.path == "/api/stream/prices")
        assert route.methods == {"GET"}


@pytest.mark.asyncio
class TestGenerateEvents:
    """Tests for the SSE event generator."""

    async def test_first_frame_is_retry_directive(self):
        cache = PriceCache()
        request = _FakeRequest(disconnect_after=0)

        events = [e async for e in _generate_events(cache, request, interval=0.01)]

        assert events[0] == "retry: 1000\n\n"

    async def test_stops_immediately_on_disconnect(self):
        cache = PriceCache()
        request = _FakeRequest(disconnect_after=0)

        events = [e async for e in _generate_events(cache, request, interval=0.01)]

        assert events == ["retry: 1000\n\n"]

    async def test_no_data_frame_when_cache_empty(self):
        cache = PriceCache()
        request = _FakeRequest(disconnect_after=1)

        events = [e async for e in _generate_events(cache, request, interval=0.01)]

        assert _data_events(events) == []

    async def test_yields_data_frame_for_cached_prices(self):
        cache = PriceCache()
        cache.update("AAPL", 190.50)
        request = _FakeRequest(disconnect_after=1)

        events = [e async for e in _generate_events(cache, request, interval=0.01)]

        data = _data_events(events)
        assert len(data) == 1
        assert data[0]["AAPL"]["price"] == 190.50
        assert data[0]["AAPL"]["ticker"] == "AAPL"

    async def test_includes_every_tracked_ticker_in_one_frame(self):
        cache = PriceCache()
        cache.update("AAPL", 190.50)
        cache.update("GOOGL", 175.25)
        request = _FakeRequest(disconnect_after=1)

        events = [e async for e in _generate_events(cache, request, interval=0.01)]

        data = _data_events(events)
        assert set(data[0].keys()) == {"AAPL", "GOOGL"}

    async def test_unchanged_version_does_not_resend(self):
        cache = PriceCache()
        cache.update("AAPL", 190.50)
        request = _FakeRequest(disconnect_after=2)

        events = [e async for e in _generate_events(cache, request, interval=0.01)]

        # Two loop iterations run but the cache never changes between them,
        # so only the first should have produced a data frame.
        assert len(_data_events(events)) == 1

    async def test_version_change_triggers_a_new_frame(self):
        cache = PriceCache()
        cache.update("AAPL", 190.50)
        request = _FakeRequest(disconnect_after=2)

        events: list[str] = []
        async for event in _generate_events(cache, request, interval=0.01):
            events.append(event)
            if event.startswith("data: ") and len(events) == 2:
                cache.update("AAPL", 191.00)

        data = _data_events(events)
        assert len(data) == 2
        assert data[0]["AAPL"]["price"] == 190.50
        assert data[1]["AAPL"]["price"] == 191.00
