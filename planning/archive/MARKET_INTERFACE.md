# Market Data Interface Design

How FinAlly abstracts "where prices come from" so the simulator and the real Massive API are
interchangeable, and downstream code (SSE stream, portfolio valuation, trade execution) never
knows or cares which one is active. This design is implemented in `backend/app/market/` — see
`planning/MARKET_DATA_SUMMARY.md` for status. This document describes the design; treat the
source files as the source of truth if the two ever disagree.

## Goal

PLAN.md Section 6 requires: simulator by default, Massive API when `MASSIVE_API_KEY` is set, and
"all downstream code ... agnostic to the source." That means one abstract contract both
implementations satisfy, one factory that picks between them, and one shared cache that
decouples producers (data sources) from consumers (SSE, portfolio math).

```
MarketDataSource (ABC)
├── SimulatorDataSource   →  GBM simulator, default, no API key needed
└── MassiveDataSource     →  Massive REST poller, used when MASSIVE_API_KEY is set
        │
        ▼
   PriceCache (thread-safe, in-memory, single instance)
        │
        ├──→ GET /api/stream/prices (SSE)
        ├──→ Portfolio valuation
        └──→ Trade execution (fill price)
```

## The Contract: `MarketDataSource`

```python
from abc import ABC, abstractmethod

class MarketDataSource(ABC):
    @abstractmethod
    async def start(self, tickers: list[str]) -> None:
        """Begin producing price updates for the given tickers.
        Starts a background task that writes to the PriceCache. Call once."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop the background task and release resources. Safe to call twice."""

    @abstractmethod
    async def add_ticker(self, ticker: str) -> None:
        """Add a ticker to the active set. No-op if already present."""

    @abstractmethod
    async def remove_ticker(self, ticker: str) -> None:
        """Remove a ticker from the active set and from the PriceCache."""

    @abstractmethod
    def get_tickers(self) -> list[str]:
        """Currently tracked tickers."""
```

Five methods, all async except the trivial getter. Both implementations own a background
`asyncio.Task` that they create in `start()` and cancel in `stop()`. Neither implementation
returns prices from its own methods — they only ever write into the shared cache. That's the
key decoupling: a caller reading a price never needs to know or branch on which source is live.

### Why an ABC and not a `Protocol`

Either would satisfy "same shape, source-agnostic callers." An ABC was chosen because there are
exactly two implementations, both owned within this project (no third-party class needs to
retroactively conform), and `abstractmethod` gives an immediate, loud `TypeError` at
instantiation if a new implementation forgets a method — a `Protocol` would only fail at the
call site, later and less clearly.

## The Shared State: `PriceCache`

```python
class PriceCache:
    def update(self, ticker: str, price: float, timestamp: float | None = None) -> PriceUpdate: ...
    def get(self, ticker: str) -> PriceUpdate | None: ...
    def get_all(self) -> dict[str, PriceUpdate]: ...
    def get_price(self, ticker: str) -> float | None: ...
    def remove(self, ticker: str) -> None: ...
    @property
    def version(self) -> int: ...  # increments on every update()
```

- One process-wide instance, created at app startup, passed by reference to whichever data
  source the factory returns and to the SSE router.
- Thread-safe (`threading.Lock`) because `MassiveDataSource` does its blocking HTTP call via
  `asyncio.to_thread`, so writes can technically originate off the event loop thread.
- `update()` computes `previous_price`/`direction`/`change` itself from whatever was already
  cached — data sources only ever pass in a new price; they never compute deltas themselves.
  This keeps that logic in one place instead of duplicated per source.
- `version` is a monotonic counter bumped on every write. The SSE endpoint polls this instead of
  diffing prices itself: cheap `int !=` check instead of comparing whole dicts every tick.

## The Data Model: `PriceUpdate`

```python
@dataclass(frozen=True, slots=True)
class PriceUpdate:
    ticker: str
    price: float
    previous_price: float
    timestamp: float = field(default_factory=time.time)  # Unix seconds

    @property
    def change(self) -> float: ...          # price - previous_price
    @property
    def change_percent(self) -> float: ...  # as a percentage
    @property
    def direction(self) -> str: ...         # "up" | "down" | "flat"

    def to_dict(self) -> dict: ...          # JSON-serializable, used directly by SSE
```

Frozen + slots: it's a point-in-time snapshot handed out by `cache.get()`/`get_all()`, never
mutated after creation, and cheap to construct on every tick for every ticker. `to_dict()`
exists so the SSE layer (and any future REST endpoint returning current prices) doesn't
reimplement the same field list.

## Selecting an Implementation: the Factory

```python
def create_market_data_source(price_cache: PriceCache) -> MarketDataSource:
    api_key = os.environ.get("MASSIVE_API_KEY", "").strip()
    if api_key:
        return MassiveDataSource(api_key=api_key, price_cache=price_cache)
    return SimulatorDataSource(price_cache=price_cache)
```

This is the *only* place that branches on `MASSIVE_API_KEY`. App startup calls this once, then
calls `await source.start(watchlist_tickers)` — from that point on, startup code, the SSE
router, and portfolio/trade code hold a `MarketDataSource` reference and never re-check which
concrete type it is. Stripping the key with `.strip()` means an accidentally-blank
`MASSIVE_API_KEY=` in `.env` correctly falls back to the simulator rather than trying (and
failing) to authenticate with an empty string.

## Implementation Notes

### `SimulatorDataSource`
Wraps a `GBMSimulator` (see `MARKET_SIMULATOR.md`). Background loop calls `sim.step()` every
500ms and writes each result into the cache. `start()` also seeds the cache synchronously before
returning, so the very first SSE payload after startup already has data — no "empty chart on
cold load" gap.

### `MassiveDataSource`
Background loop calls the Massive REST snapshot endpoint (`get_snapshot_all`) on an interval —
15s by default, matched to the free-tier rate limit (5 req/min). Same seed-before-returning
pattern in `start()`. The REST call is synchronous, so it runs via `asyncio.to_thread` to avoid
blocking the event loop for the duration of the HTTP round trip. A poll failure (bad key, rate
limit, network blip) is caught, logged, and the loop simply waits for the next interval and
retries — it does not crash the background task or propagate to callers, since a single missed
poll should never take down live price streaming for tickers whose last-known price is still
usable.

### Why both use a poll/step loop instead of push
The simulator has no external source to push from — it generates data itself, so "loop that
computes and writes" is the natural shape. The Massive integration deliberately uses REST
polling rather than a WebSocket feed, per PLAN.md Section 6: it's simpler, requires no persistent
external connection to manage/reconnect, and works uniformly across all subscription tiers
(WebSocket streaming access varies by plan; polling the snapshot endpoint does not). Giving both
sources the same "background task on an interval" shape is also what makes `start()`/`stop()`
symmetric and boringly predictable to reason about.

## Consumer: SSE Streaming

```python
def create_stream_router(price_cache: PriceCache) -> APIRouter:
    @router.get("/prices")
    async def stream_prices(request: Request) -> StreamingResponse: ...
```

The SSE generator polls `price_cache.version` every 500ms; if it changed since the last emitted
event, it serializes `get_all()` and yields one `data: {...}` frame containing *every* tracked
ticker (not a diff). Simpler client-side handling (always a full snapshot) at the cost of
re-sending unchanged tickers — acceptable given the watchlist is small (~10-30 tickers per
PLAN.md's soft-cap discussion). This is also why the Massive path's 15s poll interval and the
stream's 500ms cadence aren't in tension: the version counter means "no new data" ticks are
simply skipped, not re-sent — the stream cadence is an upper bound on latency, not a promise of
fresh data every 500ms.

## Extending: A Third Source

To add another provider (e.g. a different data vendor), implement `MarketDataSource`'s five
methods against a background task that writes into the same `PriceCache`, then add one branch to
`create_market_data_source`. Nothing in the SSE router, portfolio code, or trade execution needs
to change — that's the point of the abstraction.
