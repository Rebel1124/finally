# Market Data Backend — Design & Implementation Guide

This is the single, code-complete reference for FinAlly's market data subsystem: the unified
`MarketDataSource` interface, the GBM simulator, and the Massive (Polygon.io) REST client, plus
how they're wired into the rest of the FastAPI app.

**Status:** already implemented in `backend/app/market/` (8 modules, ~500 lines, 73 tests
passing — see `planning/MARKET_DATA_SUMMARY.md`). This document consolidates
`MARKET_INTERFACE.md`, `MARKET_SIMULATOR.md`, and `MASSIVE_API.md` into one place with full code
listings, so a reader can implement (or re-implement) the whole subsystem from this document
alone. If this document and the source under `backend/app/market/` ever disagree, **the source is
correct** — update this document to match, not the other way around.

## Table of Contents

1. [Architecture](#1-architecture)
2. [Data Model — `PriceUpdate`](#2-data-model--priceupdate)
3. [Shared State — `PriceCache`](#3-shared-state--pricecache)
4. [The Contract — `MarketDataSource`](#4-the-contract--marketdatasource)
5. [Simulator — `GBMSimulator` + `SimulatorDataSource`](#5-simulator--gbmsimulator--simulatordatasource)
6. [Massive API — `MassiveDataSource`](#6-massive-api--massivedatasource)
7. [Factory — `create_market_data_source`](#7-factory--create_market_data_source)
8. [Consumer — SSE Streaming](#8-consumer--sse-streaming)
9. [Wiring It Into the FastAPI App](#9-wiring-it-into-the-fastapi-app)
10. [Testing Approach](#10-testing-approach)
11. [Extending: A Third Source](#11-extending-a-third-source)

---

## 1. Architecture

```
MarketDataSource (ABC)
├── SimulatorDataSource  →  GBM simulator (default, no API key needed)
└── MassiveDataSource    →  Massive/Polygon.io REST poller (when MASSIVE_API_KEY is set)
        │
        ▼
   PriceCache (thread-safe, in-memory, one process-wide instance)
        │
        ├──→ GET /api/stream/prices (SSE)
        ├──→ Portfolio valuation
        └──→ Trade execution (fill price)
```

**One abstract contract**, both implementations satisfy it. **One factory** picks between them
based on `MASSIVE_API_KEY`. **One shared cache** decouples producers (data sources, which only
ever *write*) from consumers (SSE stream, portfolio math, trade fills, which only ever *read*).
Nothing downstream of the cache branches on which concrete source is active — that's the entire
point of the abstraction (PLAN.md Section 6: "all downstream code ... agnostic to the source").

Package layout (`backend/app/market/`):

| File | Purpose |
|------|---------|
| `models.py` | `PriceUpdate` — immutable price snapshot |
| `cache.py` | `PriceCache` — thread-safe store with version counter |
| `interface.py` | `MarketDataSource` — abstract base class |
| `seed_prices.py` | Seed prices, per-ticker GBM params, correlation groups |
| `simulator.py` | `GBMSimulator` (pure math) + `SimulatorDataSource` (async adapter) |
| `massive_client.py` | `MassiveDataSource` — REST polling client |
| `factory.py` | `create_market_data_source()` |
| `stream.py` | `create_stream_router()` — FastAPI SSE endpoint |
| `__init__.py` | Public exports |

---

## 2. Data Model — `PriceUpdate`

A frozen, `slots`-based dataclass: cheap to construct on every tick for every ticker, and safe to
hand out from `cache.get()` without the caller being able to mutate cache state. All derived
fields (`change`, `change_percent`, `direction`) are computed properties, not stored, so there's
never a chance of them going stale relative to `price`/`previous_price`.

```python
# app/market/models.py
"""Data models for market data."""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class PriceUpdate:
    """Immutable snapshot of a single ticker's price at a point in time."""

    ticker: str
    price: float
    previous_price: float
    timestamp: float = field(default_factory=time.time)  # Unix seconds

    @property
    def change(self) -> float:
        """Absolute price change from previous update."""
        return round(self.price - self.previous_price, 4)

    @property
    def change_percent(self) -> float:
        """Percentage change from previous update."""
        if self.previous_price == 0:
            return 0.0
        return round((self.price - self.previous_price) / self.previous_price * 100, 4)

    @property
    def direction(self) -> str:
        """'up', 'down', or 'flat'."""
        if self.price > self.previous_price:
            return "up"
        elif self.price < self.previous_price:
            return "down"
        return "flat"

    def to_dict(self) -> dict:
        """Serialize for JSON / SSE transmission."""
        return {
            "ticker": self.ticker,
            "price": self.price,
            "previous_price": self.previous_price,
            "timestamp": self.timestamp,
            "change": self.change,
            "change_percent": self.change_percent,
            "direction": self.direction,
        }
```

`to_dict()` is the single place that defines the wire format for a price — the SSE layer uses it
directly, and any future REST endpoint returning current prices (e.g. `GET /api/watchlist`
joining in live prices) should reuse it rather than re-serializing the fields by hand.

---

## 3. Shared State — `PriceCache`

```python
# app/market/cache.py
"""Thread-safe in-memory price cache."""

from __future__ import annotations

import time
from threading import Lock

from .models import PriceUpdate


class PriceCache:
    """Thread-safe in-memory cache of the latest price for each ticker.

    Writers: SimulatorDataSource or MassiveDataSource (one at a time).
    Readers: SSE streaming endpoint, portfolio valuation, trade execution.
    """

    def __init__(self) -> None:
        self._prices: dict[str, PriceUpdate] = {}
        self._lock = Lock()
        self._version: int = 0  # Monotonically increasing; bumped on every update

    def update(self, ticker: str, price: float, timestamp: float | None = None) -> PriceUpdate:
        """Record a new price for a ticker. Returns the created PriceUpdate.

        Automatically computes direction and change from the previous price.
        If this is the first update for the ticker, previous_price == price (direction='flat').
        """
        with self._lock:
            ts = timestamp or time.time()
            prev = self._prices.get(ticker)
            previous_price = prev.price if prev else price

            update = PriceUpdate(
                ticker=ticker,
                price=round(price, 2),
                previous_price=round(previous_price, 2),
                timestamp=ts,
            )
            self._prices[ticker] = update
            self._version += 1
            return update

    def get(self, ticker: str) -> PriceUpdate | None:
        """Get the latest price for a single ticker, or None if unknown."""
        with self._lock:
            return self._prices.get(ticker)

    def get_all(self) -> dict[str, PriceUpdate]:
        """Snapshot of all current prices. Returns a shallow copy."""
        with self._lock:
            return dict(self._prices)

    def get_price(self, ticker: str) -> float | None:
        """Convenience: get just the price float, or None."""
        update = self.get(ticker)
        return update.price if update else None

    def remove(self, ticker: str) -> None:
        """Remove a ticker from the cache (e.g., when removed from watchlist)."""
        with self._lock:
            self._prices.pop(ticker, None)

    @property
    def version(self) -> int:
        """Current version counter. Useful for SSE change detection."""
        return self._version

    def __len__(self) -> int:
        with self._lock:
            return len(self._prices)

    def __contains__(self, ticker: str) -> bool:
        with self._lock:
            return ticker in self._prices
```

Design points worth calling out when implementing this from scratch:

- **Why a `Lock` at all in an asyncio app.** `MassiveDataSource` runs its blocking HTTP call via
  `asyncio.to_thread`, so the write that follows can originate off the event loop thread. A plain
  `dict` write is not atomic enough to trust across threads; a `threading.Lock` is cheap and
  correct here (uncontended in practice — one writer, occasional readers).
- **`update()` computes the delta, not the caller.** Data sources only ever pass in a *new*
  price; `PriceCache` looks up whatever was previously cached and derives `previous_price`. This
  keeps "what does a price change even mean" logic in exactly one place instead of duplicated in
  the simulator and the Massive client.
- **`version` instead of dict-diffing.** The SSE loop (Section 8) needs to know "did anything
  change since I last sent a frame?" A monotonic `int` bumped on every `update()` call turns that
  into a cheap `!=` check every tick instead of comparing whole price dicts.

---

## 4. The Contract — `MarketDataSource`

```python
# app/market/interface.py
"""Abstract interface for market data sources."""

from __future__ import annotations

from abc import ABC, abstractmethod


class MarketDataSource(ABC):
    """Contract for market data providers.

    Implementations push price updates into a shared PriceCache on their own
    schedule. Downstream code never calls the data source directly for prices —
    it reads from the cache.

    Lifecycle:
        source = create_market_data_source(cache)
        await source.start(["AAPL", "GOOGL", ...])
        # ... app runs ...
        await source.add_ticker("TSLA")
        await source.remove_ticker("GOOGL")
        # ... app shutting down ...
        await source.stop()
    """

    @abstractmethod
    async def start(self, tickers: list[str]) -> None:
        """Begin producing price updates for the given tickers.

        Starts a background task that periodically writes to the PriceCache.
        Must be called exactly once. Calling start() twice is undefined behavior.
        """

    @abstractmethod
    async def stop(self) -> None:
        """Stop the background task and release resources.

        Safe to call multiple times. After stop(), the source will not write
        to the cache again.
        """

    @abstractmethod
    async def add_ticker(self, ticker: str) -> None:
        """Add a ticker to the active set. No-op if already present.

        The next update cycle will include this ticker.
        """

    @abstractmethod
    async def remove_ticker(self, ticker: str) -> None:
        """Remove a ticker from the active set. No-op if not present.

        Also removes the ticker from the PriceCache.
        """

    @abstractmethod
    def get_tickers(self) -> list[str]:
        """Return the current list of actively tracked tickers."""
```

**Five methods, all async except the trivial getter.** Both implementations own a background
`asyncio.Task` created in `start()` and cancelled in `stop()`. Neither implementation *returns*
prices from its own methods — they only ever write into the shared cache. A caller reading a
price never needs to know or branch on which source is live.

**Why an ABC and not a `Protocol`.** Either would satisfy "same shape, source-agnostic callers."
An ABC was chosen because there are exactly two implementations, both owned within this project
(no third-party class needs to retroactively conform), and `abstractmethod` gives an immediate,
loud `TypeError` at instantiation if a new implementation forgets a method — a `Protocol` would
only fail at the call site, later and less clearly.

---

## 5. Simulator — `GBMSimulator` + `SimulatorDataSource`

### 5.1 Why Geometric Brownian Motion

GBM is the standard model behind Black-Scholes and most retail-facing price simulators: prices
are log-normally distributed (so they never go negative), moves compound multiplicatively, and
two parameters per ticker — drift (`mu`) and volatility (`sigma`) — are enough to make a stock
"feel" like itself (TSLA choppier than JPM) without hand-authoring per-tick behavior.

```
S(t+dt) = S(t) * exp((mu - sigma^2/2) * dt + sigma * sqrt(dt) * Z)
```

- `S(t)` — current price
- `mu` — annualized drift (expected return)
- `sigma` — annualized volatility
- `dt` — time step, expressed as a fraction of a trading year
- `Z` — a standard normal random draw (correlated across tickers, below)

The `- sigma^2/2` term is the standard Itô correction so `mu` remains the actual expected
*arithmetic* return despite log-normal compounding.

### 5.2 Time step

The simulator ticks every 500ms (matching the SSE cadence), so `dt` is 500ms expressed as a
fraction of a 252-day, 6.5-hour trading year:

```python
TRADING_SECONDS_PER_YEAR = 252 * 6.5 * 3600  # 5,896,800
DEFAULT_DT = 0.5 / TRADING_SECONDS_PER_YEAR   # ≈ 8.48e-8
```

At this `dt`, each individual tick moves a price by a fraction of a cent on average — prices
drift smoothly rather than jumping, which is what makes sparklines and flash animations look
natural instead of jittery.

### 5.3 Correlated moves

Real markets don't move ticker-by-ticker independently. Each tick draws one independent
standard-normal vector (one value per ticker), then applies the Cholesky decomposition of a
correlation matrix to turn it into a correlated vector:

```python
z_independent = np.random.standard_normal(n)
z_correlated = cholesky_matrix @ z_independent
```

Correlation structure, sector-based:

| Pairing | Correlation |
|---|---|
| Two tech tickers (AAPL, GOOGL, MSFT, AMZN, META, NVDA, NFLX) | 0.6 |
| Two finance tickers (JPM, V) | 0.5 |
| Either side is TSLA | 0.3 ("does its own thing") |
| Cross-sector, or either ticker unrecognized | 0.3 |

The Cholesky matrix is rebuilt whenever a ticker is added or removed (infrequent — O(n²) rebuild
on a <50-ticker list is negligible) and reused across every tick in between (`step()` is the hot
path, running twice a second — it must stay cheap).

### 5.4 Seed data — `seed_prices.py`

Seed prices and `(mu, sigma)` live in one static table so tuning "how wiggly does TSLA feel" is a
one-line data change, not a code change:

```python
# app/market/seed_prices.py
"""Seed prices and per-ticker parameters for the market simulator."""

# Realistic starting prices for the default watchlist (as of project creation)
SEED_PRICES: dict[str, float] = {
    "AAPL": 190.00,
    "GOOGL": 175.00,
    "MSFT": 420.00,
    "AMZN": 185.00,
    "TSLA": 250.00,
    "NVDA": 800.00,
    "META": 500.00,
    "JPM": 195.00,
    "V": 280.00,
    "NFLX": 600.00,
}

# Per-ticker GBM parameters
# sigma: annualized volatility (higher = more price movement)
# mu: annualized drift / expected return
TICKER_PARAMS: dict[str, dict[str, float]] = {
    "AAPL": {"sigma": 0.22, "mu": 0.05},
    "GOOGL": {"sigma": 0.25, "mu": 0.05},
    "MSFT": {"sigma": 0.20, "mu": 0.05},
    "AMZN": {"sigma": 0.28, "mu": 0.05},
    "TSLA": {"sigma": 0.50, "mu": 0.03},  # High volatility
    "NVDA": {"sigma": 0.40, "mu": 0.08},  # High volatility, strong drift
    "META": {"sigma": 0.30, "mu": 0.05},
    "JPM": {"sigma": 0.18, "mu": 0.04},  # Low volatility (bank)
    "V": {"sigma": 0.17, "mu": 0.04},  # Low volatility (payments)
    "NFLX": {"sigma": 0.35, "mu": 0.05},
}

# Default parameters for tickers not in the list above (dynamically added)
DEFAULT_PARAMS: dict[str, float] = {"sigma": 0.25, "mu": 0.05}

# Correlation groups for the simulator's Cholesky decomposition
# Tickers in the same group have higher intra-group correlation
CORRELATION_GROUPS: dict[str, set[str]] = {
    "tech": {"AAPL", "GOOGL", "MSFT", "AMZN", "META", "NVDA", "NFLX"},
    "finance": {"JPM", "V"},
}

# Correlation coefficients
INTRA_TECH_CORR = 0.6  # Tech stocks move together
INTRA_FINANCE_CORR = 0.5  # Finance stocks move together
CROSS_GROUP_CORR = 0.3  # Between sectors / unknown tickers
TSLA_CORR = 0.3  # TSLA does its own thing
```

A ticker added at runtime that isn't in `SEED_PRICES`/`TICKER_PARAMS` (e.g. a user adds an
arbitrary symbol via chat or the watchlist UI) falls back to a random seed price in `[50, 300]`
and `DEFAULT_PARAMS` — the goal is "looks plausible," not "matches the real security."

### 5.5 Random events

On top of continuous GBM drift, each ticker has a small independent chance per tick of a sudden
jump, purely for visual drama:

```python
event_probability = 0.001  # 0.1% per tick per ticker
if random.random() < event_probability:
    shock_magnitude = random.uniform(0.02, 0.05)   # 2-5%
    shock_sign = random.choice([-1, 1])
    price *= 1 + shock_magnitude * shock_sign
```

With 10 tickers ticking twice a second, that's roughly one shock event somewhere in the watchlist
every ~50 seconds — frequent enough to be noticeable in a live demo, rare enough not to feel
gimmicky.

### 5.6 Full implementation

`GBMSimulator` is pure, synchronous math — no async, no I/O, no cache access — which makes it
trivial to unit test (seed it, call `step()`, assert on the output distribution, no event loop or
mocking needed). `SimulatorDataSource` is the thin async adapter that satisfies
`MarketDataSource` and is the only piece that touches `asyncio` or the `PriceCache`. This mirrors
the split in `MassiveDataSource` (Section 6) — both concrete sources separate "produce a price"
from "run on a schedule and publish it," even though one computes prices and the other fetches
them.

```python
# app/market/simulator.py
"""GBM-based market simulator."""

from __future__ import annotations

import asyncio
import logging
import math
import random

import numpy as np

from .cache import PriceCache
from .interface import MarketDataSource
from .seed_prices import (
    CORRELATION_GROUPS,
    CROSS_GROUP_CORR,
    DEFAULT_PARAMS,
    INTRA_FINANCE_CORR,
    INTRA_TECH_CORR,
    SEED_PRICES,
    TICKER_PARAMS,
    TSLA_CORR,
)

logger = logging.getLogger(__name__)


class GBMSimulator:
    """Geometric Brownian Motion simulator for correlated stock prices.

    Math:
        S(t+dt) = S(t) * exp((mu - sigma^2/2) * dt + sigma * sqrt(dt) * Z)

    Where:
        S(t)   = current price
        mu     = annualized drift (expected return)
        sigma  = annualized volatility
        dt     = time step as fraction of a trading year
        Z      = correlated standard normal random variable

    The tiny dt (~8.5e-8 for 500ms ticks over 252 trading days * 6.5h/day)
    produces sub-cent moves per tick that accumulate naturally over time.
    """

    # 500ms expressed as a fraction of a trading year
    # 252 trading days * 6.5 hours/day * 3600 seconds/hour = 5,896,800 seconds
    TRADING_SECONDS_PER_YEAR = 252 * 6.5 * 3600  # 5,896,800
    DEFAULT_DT = 0.5 / TRADING_SECONDS_PER_YEAR  # ~8.48e-8

    def __init__(
        self,
        tickers: list[str],
        dt: float = DEFAULT_DT,
        event_probability: float = 0.001,
    ) -> None:
        self._dt = dt
        self._event_prob = event_probability

        # Per-ticker state
        self._tickers: list[str] = []
        self._prices: dict[str, float] = {}
        self._params: dict[str, dict[str, float]] = {}

        # Cholesky decomposition of the correlation matrix (for correlated moves)
        self._cholesky: np.ndarray | None = None

        # Initialize all starting tickers
        for ticker in tickers:
            self._add_ticker_internal(ticker)
        self._rebuild_cholesky()

    # --- Public API ---

    def step(self) -> dict[str, float]:
        """Advance all tickers by one time step. Returns {ticker: new_price}.

        This is the hot path — called every 500ms. Keep it fast.
        """
        n = len(self._tickers)
        if n == 0:
            return {}

        # Generate n independent standard normal draws
        z_independent = np.random.standard_normal(n)

        # Apply Cholesky to get correlated draws
        if self._cholesky is not None:
            z_correlated = self._cholesky @ z_independent
        else:
            z_correlated = z_independent

        result: dict[str, float] = {}
        for i, ticker in enumerate(self._tickers):
            params = self._params[ticker]
            mu = params["mu"]
            sigma = params["sigma"]

            # GBM: S(t+dt) = S(t) * exp((mu - 0.5*sigma^2)*dt + sigma*sqrt(dt)*Z)
            drift = (mu - 0.5 * sigma**2) * self._dt
            diffusion = sigma * math.sqrt(self._dt) * z_correlated[i]
            self._prices[ticker] *= math.exp(drift + diffusion)

            # Random event: ~0.1% chance per tick per ticker
            # With 10 tickers at 2 ticks/sec, expect an event ~every 50 seconds
            if random.random() < self._event_prob:
                shock_magnitude = random.uniform(0.02, 0.05)
                shock_sign = random.choice([-1, 1])
                self._prices[ticker] *= 1 + shock_magnitude * shock_sign
                logger.debug(
                    "Random event on %s: %.1f%% %s",
                    ticker,
                    shock_magnitude * 100,
                    "up" if shock_sign > 0 else "down",
                )

            result[ticker] = round(self._prices[ticker], 2)

        return result

    def add_ticker(self, ticker: str) -> None:
        """Add a ticker to the simulation. Rebuilds the correlation matrix."""
        if ticker in self._prices:
            return
        self._add_ticker_internal(ticker)
        self._rebuild_cholesky()

    def remove_ticker(self, ticker: str) -> None:
        """Remove a ticker from the simulation. Rebuilds the correlation matrix."""
        if ticker not in self._prices:
            return
        self._tickers.remove(ticker)
        del self._prices[ticker]
        del self._params[ticker]
        self._rebuild_cholesky()

    def get_price(self, ticker: str) -> float | None:
        """Current price for a ticker, or None if not tracked."""
        return self._prices.get(ticker)

    def get_tickers(self) -> list[str]:
        """Return the list of currently tracked tickers."""
        return list(self._tickers)

    # --- Internals ---

    def _add_ticker_internal(self, ticker: str) -> None:
        """Add a ticker without rebuilding Cholesky (for batch initialization)."""
        if ticker in self._prices:
            return
        self._tickers.append(ticker)
        self._prices[ticker] = SEED_PRICES.get(ticker, random.uniform(50.0, 300.0))
        self._params[ticker] = TICKER_PARAMS.get(ticker, dict(DEFAULT_PARAMS))

    def _rebuild_cholesky(self) -> None:
        """Rebuild the Cholesky decomposition of the ticker correlation matrix.

        Called whenever tickers are added or removed. O(n^2) but n < 50.
        """
        n = len(self._tickers)
        if n <= 1:
            self._cholesky = None
            return

        # Build the correlation matrix
        corr = np.eye(n)
        for i in range(n):
            for j in range(i + 1, n):
                rho = self._pairwise_correlation(self._tickers[i], self._tickers[j])
                corr[i, j] = rho
                corr[j, i] = rho

        self._cholesky = np.linalg.cholesky(corr)

    @staticmethod
    def _pairwise_correlation(t1: str, t2: str) -> float:
        """Determine correlation between two tickers based on sector grouping.

        Correlation structure:
          - Same tech sector:   0.6
          - Same finance sector: 0.5
          - TSLA with anything: 0.3 (it does its own thing)
          - Cross-sector:       0.3
          - Unknown tickers:    0.3
        """
        tech = CORRELATION_GROUPS["tech"]
        finance = CORRELATION_GROUPS["finance"]

        # TSLA is in tech set but behaves independently
        if t1 == "TSLA" or t2 == "TSLA":
            return TSLA_CORR

        if t1 in tech and t2 in tech:
            return INTRA_TECH_CORR
        if t1 in finance and t2 in finance:
            return INTRA_FINANCE_CORR

        return CROSS_GROUP_CORR


class SimulatorDataSource(MarketDataSource):
    """MarketDataSource backed by the GBM simulator.

    Runs a background asyncio task that calls GBMSimulator.step() every
    `update_interval` seconds and writes results to the PriceCache.
    """

    def __init__(
        self,
        price_cache: PriceCache,
        update_interval: float = 0.5,
        event_probability: float = 0.001,
    ) -> None:
        self._cache = price_cache
        self._interval = update_interval
        self._event_prob = event_probability
        self._sim: GBMSimulator | None = None
        self._task: asyncio.Task | None = None

    async def start(self, tickers: list[str]) -> None:
        self._sim = GBMSimulator(
            tickers=tickers,
            event_probability=self._event_prob,
        )
        # Seed the cache with initial prices so SSE has data immediately
        for ticker in tickers:
            price = self._sim.get_price(ticker)
            if price is not None:
                self._cache.update(ticker=ticker, price=price)
        self._task = asyncio.create_task(self._run_loop(), name="simulator-loop")
        logger.info("Simulator started with %d tickers", len(tickers))

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        logger.info("Simulator stopped")

    async def add_ticker(self, ticker: str) -> None:
        if self._sim:
            self._sim.add_ticker(ticker)
            # Seed cache immediately so the ticker has a price right away
            price = self._sim.get_price(ticker)
            if price is not None:
                self._cache.update(ticker=ticker, price=price)
            logger.info("Simulator: added ticker %s", ticker)

    async def remove_ticker(self, ticker: str) -> None:
        if self._sim:
            self._sim.remove_ticker(ticker)
        self._cache.remove(ticker)
        logger.info("Simulator: removed ticker %s", ticker)

    def get_tickers(self) -> list[str]:
        return self._sim.get_tickers() if self._sim else []

    async def _run_loop(self) -> None:
        """Core loop: step the simulation, write to cache, sleep."""
        while True:
            try:
                if self._sim:
                    prices = self._sim.step()
                    for ticker, price in prices.items():
                        self._cache.update(ticker=ticker, price=price)
            except Exception:
                logger.exception("Simulator step failed")
            await asyncio.sleep(self._interval)
```

A step failure is caught and logged rather than allowed to kill the background task — one bad
tick shouldn't take down price streaming for the rest of the session; the loop just tries again
500ms later. Same pattern in `MassiveDataSource._poll_once` (Section 6).

### 5.7 Non-goals

- **Not a market microstructure simulator.** No order book, no bid/ask spread modeling, no
  volume simulation feeding into price impact. FinAlly only needs a plausible last-trade price
  per tick, per PLAN.md's "market orders only, instant fill" design.
- **Not calibrated to real historical volatility.** `sigma`/`mu` values are chosen to *feel*
  right in a live demo (distinguishable ticker personalities), not fit from real return series.

---

## 6. Massive API — `MassiveDataSource`

### 6.1 Provider background

[Massive](https://massive.com) is the rebranded name (as of 2025-10-30) of Polygon.io. Existing
Polygon.io API keys and the `api.polygon.io` host still work; the official SDK now defaults to
`api.massive.com`. FinAlly uses the official Python client, package name `massive`:

```bash
uv add massive
```

Requires Python >=3.9. Repo: [massive-com/client-python](https://github.com/massive-com/client-python).

```python
from massive import RESTClient

client = RESTClient(api_key="YOUR_KEY")  # or set POLYGON_API_KEY / pass explicitly
```

FinAlly stores the key in `MASSIVE_API_KEY` (project convention, not a client-library default —
read it explicitly with `os.environ`), never builds raw HTTP calls by hand.

### 6.2 Rate limits

| Tier | Cost | REST limit | History | Data freshness |
|---|---|---|---|---|
| Basic (free) | $0/mo | 5 requests/min | 2 years | End-of-day only |
| Starter | $29/mo | Unlimited | 5 years | 15-minute delayed |
| Developer | $79/mo | Unlimited | 10 years | 15-minute delayed, includes trades |
| Advanced | $199/mo | Unlimited | 20+ years | Real-time, quotes, financials |

On the free tier, snapshot data is **not real-time** — it's whatever the last end-of-day close
was, refreshed once daily. A poll interval faster than 15s buys nothing extra on this tier; it
only matters once trades data / real-time is unlocked on a paid plan. This is why
`MassiveDataSource` defaults to a 15s poll interval, matched to the 5 req/min free-tier limit.

### 6.3 Endpoint used — Full Market Snapshot

```
GET /v2/snapshot/locale/us/markets/stocks/tickers
```

One call covers the entire watchlist — exactly what a single background poller needs.

**Query parameters:**
- `tickers` — case-sensitive comma-separated list, e.g. `AAPL,GOOGL,MSFT`. Always pass an
  explicit list (omitting it returns all 10,000+ active tickers).
- `include_otc` — bool, default `false`.

**Response shape** (`tickers[]`, one object per requested ticker):

```json
{
  "status": "OK",
  "count": 3,
  "tickers": [
    {
      "ticker": "AAPL",
      "todaysChange": 1.23,
      "todaysChangePerc": 0.65,
      "updated": 1735689600000000000,
      "day":     { "o": 189.5, "h": 191.2, "l": 188.9, "c": 190.7, "v": 41200000, "vw": 190.1 },
      "prevDay": { "o": 187.0, "h": 189.9, "l": 186.5, "c": 189.47, "v": 39800000, "vw": 188.2 },
      "min":     { "o": 190.6, "h": 190.8, "l": 190.5, "c": 190.7, "v": 12500, "t": 1735689600000 },
      "lastTrade": { "p": 190.72, "s": 100, "t": 1735689612345678900 },
      "lastQuote": { "P": 190.73, "p": 190.71, "S": 200, "s": 300, "t": 1735689612300000000 }
    }
  ]
}
```

The only field FinAlly's price feed depends on is `lastTrade.p` (price) and `lastTrade.t`
(timestamp) — `day`/`prevDay` are not currently consumed since `PriceCache.update()` computes
`change`/`direction` itself from the previously cached price.

```python
from massive import RESTClient
from massive.rest.models import SnapshotMarketType

client = RESTClient(api_key="YOUR_KEY")

snapshots = client.get_snapshot_all(
    market_type=SnapshotMarketType.STOCKS,
    tickers=["AAPL", "GOOGL", "MSFT"],
)

for snap in snapshots:
    print(snap.ticker, snap.last_trade.price, snap.last_trade.sip_timestamp)
```

`get_snapshot_all` is **synchronous** (blocking network I/O) — in an asyncio app, run it via
`asyncio.to_thread(...)` rather than calling it directly on the event loop.

**Timestamp field and units.** The typed Python client's `LastTrade` model (installed `massive`
v2.2.0) has **no `.timestamp` attribute** — verified directly against the installed SDK, not just
its docs. The raw REST payload's nanosecond `t` field is exposed as `last_trade.sip_timestamp`
instead. `MassiveDataSource` reads `sip_timestamp` and divides by `1e9` to get Unix seconds.

### 6.4 Endpoints considered but not used

- **`GET /v3/snapshot`** (Unified Snapshot) — cross-asset-class (`ticker.any_of=AAPL,MSFT`, up to
  250 tickers). More general than the stocks-only snapshot, but real-time data on this endpoint
  requires Advanced/Business plans. Not used — the stocks-only full-market-snapshot is simpler
  and sufficient for a single-asset-class watchlist.
- **`GET /v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/{from}/{to}`** (Aggregate Bars) —
  historical/EOD OHLC bars. Useful for a future "seed a chart with real closing prices" or
  backtest feature, but not needed today since charts are built client-side from the SSE stream
  (PLAN.md Section 10). No batch/multi-ticker variant exists — one call per ticker per date
  range. Reach for this endpoint specifically if that future feature gets built; see
  `MASSIVE_API.md` for the full parameter reference and a `list_aggs` usage example.

### 6.5 Error handling notes

- `401` — bad/missing API key.
- `429` — rate limit exceeded (free tier: >5 req/min).
- Snapshot fields can be partially missing for illiquid tickers or just after market open (e.g.
  no `min` bar yet) — treat `lastTrade` as the only field safe to assume present, and skip/log a
  ticker whose snapshot is malformed rather than letting one bad ticker crash the whole poll
  cycle.

### 6.6 Full implementation

```python
# app/market/massive_client.py
"""Massive (Polygon.io) API client for real market data."""

from __future__ import annotations

import asyncio
import logging

from massive import RESTClient
from massive.rest.models import SnapshotMarketType

from .cache import PriceCache
from .interface import MarketDataSource

logger = logging.getLogger(__name__)


class MassiveDataSource(MarketDataSource):
    """MarketDataSource backed by the Massive (Polygon.io) REST API.

    Polls GET /v2/snapshot/locale/us/markets/stocks/tickers for all watched
    tickers in a single API call, then writes results to the PriceCache.

    Rate limits:
      - Free tier: 5 req/min → poll every 15s (default)
      - Paid tiers: higher limits → poll every 2-5s
    """

    def __init__(
        self,
        api_key: str,
        price_cache: PriceCache,
        poll_interval: float = 15.0,
    ) -> None:
        self._api_key = api_key
        self._cache = price_cache
        self._interval = poll_interval
        self._tickers: list[str] = []
        self._task: asyncio.Task | None = None
        self._client: RESTClient | None = None

    async def start(self, tickers: list[str]) -> None:
        self._client = RESTClient(api_key=self._api_key)
        self._tickers = list(tickers)

        # Do an immediate first poll so the cache has data right away
        await self._poll_once()

        self._task = asyncio.create_task(self._poll_loop(), name="massive-poller")
        logger.info(
            "Massive poller started: %d tickers, %.1fs interval",
            len(tickers),
            self._interval,
        )

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        self._client = None
        logger.info("Massive poller stopped")

    async def add_ticker(self, ticker: str) -> None:
        ticker = ticker.upper().strip()
        if ticker not in self._tickers:
            self._tickers.append(ticker)
            logger.info("Massive: added ticker %s (will appear on next poll)", ticker)

    async def remove_ticker(self, ticker: str) -> None:
        ticker = ticker.upper().strip()
        self._tickers = [t for t in self._tickers if t != ticker]
        self._cache.remove(ticker)
        logger.info("Massive: removed ticker %s", ticker)

    def get_tickers(self) -> list[str]:
        return list(self._tickers)

    # --- Internal ---

    async def _poll_loop(self) -> None:
        """Poll on interval. First poll already happened in start()."""
        while True:
            await asyncio.sleep(self._interval)
            await self._poll_once()

    async def _poll_once(self) -> None:
        """Execute one poll cycle: fetch snapshots, update cache."""
        if not self._tickers or not self._client:
            return

        try:
            # The Massive RESTClient is synchronous — run in a thread to
            # avoid blocking the event loop.
            snapshots = await asyncio.to_thread(self._fetch_snapshots)
            processed = 0
            for snap in snapshots:
                try:
                    price = snap.last_trade.price
                    # sip_timestamp is Unix nanoseconds → convert to seconds
                    timestamp = snap.last_trade.sip_timestamp / 1_000_000_000.0
                    self._cache.update(
                        ticker=snap.ticker,
                        price=price,
                        timestamp=timestamp,
                    )
                    processed += 1
                except (AttributeError, TypeError) as e:
                    logger.warning(
                        "Skipping snapshot for %s: %s",
                        getattr(snap, "ticker", "???"),
                        e,
                    )
            logger.debug("Massive poll: updated %d/%d tickers", processed, len(self._tickers))

        except Exception as e:
            logger.error("Massive poll failed: %s", e)
            # Don't re-raise — the loop will retry on the next interval.
            # Common failures: 401 (bad key), 429 (rate limit), network errors.

    def _fetch_snapshots(self) -> list:
        """Synchronous call to the Massive REST API. Runs in a thread."""
        return self._client.get_snapshot_all(
            market_type=SnapshotMarketType.STOCKS,
            tickers=self._tickers,
        )
```

### 6.7 Why polling instead of a push/WebSocket feed

The simulator has no external source to push from — it generates data itself, so "loop that
computes and writes" is the natural shape. The Massive integration deliberately uses REST
polling rather than a WebSocket feed, per PLAN.md Section 6: it's simpler, requires no persistent
external connection to manage/reconnect, and works uniformly across all subscription tiers
(WebSocket streaming access varies by plan; polling the snapshot endpoint does not). Giving both
sources the same "background task on an interval" shape is also what makes `start()`/`stop()`
symmetric and boringly predictable to reason about across both implementations.

---

## 7. Factory — `create_market_data_source`

```python
# app/market/factory.py
"""Factory for creating market data sources."""

from __future__ import annotations

import logging
import os

from .cache import PriceCache
from .interface import MarketDataSource
from .massive_client import MassiveDataSource
from .simulator import SimulatorDataSource

logger = logging.getLogger(__name__)


def create_market_data_source(price_cache: PriceCache) -> MarketDataSource:
    """Create the appropriate market data source based on environment variables.

    - MASSIVE_API_KEY set and non-empty → MassiveDataSource (real market data)
    - Otherwise → SimulatorDataSource (GBM simulation)

    Returns an unstarted source. Caller must await source.start(tickers).
    """
    api_key = os.environ.get("MASSIVE_API_KEY", "").strip()

    if api_key:
        logger.info("Market data source: Massive API (real data)")
        return MassiveDataSource(api_key=api_key, price_cache=price_cache)
    else:
        logger.info("Market data source: GBM Simulator")
        return SimulatorDataSource(price_cache=price_cache)
```

This is the **only** place that branches on `MASSIVE_API_KEY`. App startup calls this once, then
calls `await source.start(watchlist_tickers)` — from that point on, startup code, the SSE router,
and portfolio/trade code hold a `MarketDataSource` reference and never re-check which concrete
type it is. `.strip()` means an accidentally-blank `MASSIVE_API_KEY=` in `.env` correctly falls
back to the simulator rather than trying (and failing) to authenticate with an empty string.

---

## 8. Consumer — SSE Streaming

```python
# app/market/stream.py
"""SSE streaming endpoint for live price updates."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from .cache import PriceCache

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/stream", tags=["streaming"])


def create_stream_router(price_cache: PriceCache) -> APIRouter:
    """Create the SSE streaming router with a reference to the price cache.

    This factory pattern lets us inject the PriceCache without globals.
    """

    @router.get("/prices")
    async def stream_prices(request: Request) -> StreamingResponse:
        """SSE endpoint for live price updates.

        Streams all tracked ticker prices every ~500ms. The client connects
        with EventSource and receives events in the format:

            data: {"AAPL": {"ticker": "AAPL", "price": 190.50, ...}, ...}

        Includes a retry directive so the browser auto-reconnects on
        disconnection (EventSource built-in behavior).
        """
        return StreamingResponse(
            _generate_events(price_cache, request),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # Disable nginx buffering if proxied
            },
        )

    return router


async def _generate_events(
    price_cache: PriceCache,
    request: Request,
    interval: float = 0.5,
) -> AsyncGenerator[str, None]:
    """Async generator that yields SSE-formatted price events.

    Sends all prices every `interval` seconds. Stops when the client
    disconnects (detected via request.is_disconnected()).
    """
    # Tell the client to retry after 1 second if the connection drops
    yield "retry: 1000\n\n"

    last_version = -1
    client_ip = request.client.host if request.client else "unknown"
    logger.info("SSE client connected: %s", client_ip)

    try:
        while True:
            # Check for client disconnect
            if await request.is_disconnected():
                logger.info("SSE client disconnected: %s", client_ip)
                break

            current_version = price_cache.version
            if current_version != last_version:
                last_version = current_version
                prices = price_cache.get_all()

                if prices:
                    data = {ticker: update.to_dict() for ticker, update in prices.items()}
                    payload = json.dumps(data)
                    yield f"data: {payload}\n\n"

            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        logger.info("SSE stream cancelled for: %s", client_ip)
```

The generator polls `price_cache.version` every 500ms; if it changed since the last emitted
event, it serializes `get_all()` and yields one `data: {...}` frame containing **every** tracked
ticker (not a diff). Simpler client-side handling (always a full snapshot) at the cost of
re-sending unchanged tickers — acceptable given the watchlist is small (~10-30 tickers per
PLAN.md's soft-cap discussion).

This is also why the Massive path's 15s poll interval and the stream's 500ms cadence aren't in
tension: the version counter means "no new data" ticks are simply skipped, not re-sent — the
stream cadence is an upper bound on latency, not a promise of fresh data every 500ms.

**Frontend usage** (per PLAN.md Section 10):

```typescript
const es = new EventSource("/api/stream/prices");
es.onmessage = (event) => {
  const prices: Record<string, PriceUpdateDto> = JSON.parse(event.data);
  // prices["AAPL"] = { ticker, price, previous_price, timestamp, change, change_percent, direction }
};
// EventSource has built-in reconnection; the `retry: 1000` directive controls the delay.
```

---

## 9. Wiring It Into the FastAPI App

The rest of the backend (`app/main.py`, DB, portfolio, chat) is not yet built as of this
document. This section specifies how the market data subsystem plugs into a FastAPI app once it
exists, so the integration point is unambiguous for whoever builds `main.py`.

### 9.1 App lifespan

`PriceCache` and the `MarketDataSource` are process-wide singletons, created once at startup and
torn down at shutdown, using FastAPI's `lifespan` context manager (not a global at import time —
that would make testing with a fresh cache per test harder).

```python
# app/main.py (illustrative — backend/db and other routers omitted)
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.market import PriceCache, create_market_data_source, create_stream_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    price_cache = PriceCache()
    market_source = create_market_data_source(price_cache)

    # Watchlist tickers come from the DB (seeded defaults on first run — see
    # PLAN.md Section 7). This lazily initializes the DB if needed and
    # returns the current watchlist for the single "default" user.
    tickers = await get_watchlist_tickers()  # e.g. AAPL, GOOGL, MSFT, ...
    await market_source.start(tickers)

    # Make both available to request handlers via app.state
    app.state.price_cache = price_cache
    app.state.market_source = market_source

    yield

    await market_source.stop()


app = FastAPI(lifespan=lifespan)
app.include_router(create_stream_router(app.state.price_cache))
```

A subtlety: `app.state.price_cache` is only set *inside* `lifespan`, but
`create_stream_router(...)` is called at module scope right after `app = FastAPI(...)` in the
snippet above — that ordering is wrong (`app.state.price_cache` won't exist yet). In the real
`main.py`, mount routers that need the cache either by:

- Constructing the `PriceCache` **before** `FastAPI(lifespan=...)` (it's a plain object with no
  I/O in `__init__`, so this is safe) and closing over that same instance in both `lifespan` and
  `create_stream_router`, or
- Using a dependency (`Depends`) that reads `request.app.state.price_cache` instead of a
  router factory that captures the cache at include-time.

The first option is simpler and matches how `create_market_data_source` is already written to
take a `PriceCache` instance rather than construct its own:

```python
price_cache = PriceCache()  # module scope, before FastAPI(...)

@asynccontextmanager
async def lifespan(app: FastAPI):
    market_source = create_market_data_source(price_cache)
    tickers = await get_watchlist_tickers()
    await market_source.start(tickers)
    app.state.market_source = market_source
    yield
    await market_source.stop()

app = FastAPI(lifespan=lifespan)
app.include_router(create_stream_router(price_cache))
```

### 9.2 Watchlist mutation (`POST /api/watchlist`, `DELETE /api/watchlist/{ticker}`)

Watchlist routes must keep three things in sync: the `watchlist` DB table, the running
`MarketDataSource`, and (implicitly) the `PriceCache`, which the data source already updates as
part of `add_ticker`/`remove_ticker`. Route handlers never touch `PriceCache` directly — only the
`MarketDataSource` does, per the architecture in Section 1.

```python
@app.post("/api/watchlist")
async def add_to_watchlist(body: AddTickerRequest, request: Request):
    ticker = body.ticker.upper().strip()
    await db_add_watchlist_ticker(ticker)  # persists to SQLite
    await request.app.state.market_source.add_ticker(ticker)
    return {"ticker": ticker}


@app.delete("/api/watchlist/{ticker}")
async def remove_from_watchlist(ticker: str, request: Request):
    ticker = ticker.upper().strip()
    await db_remove_watchlist_ticker(ticker)
    await request.app.state.market_source.remove_ticker(ticker)
    return {"ticker": ticker}
```

### 9.3 Reading current prices (portfolio valuation, trade fills)

Portfolio valuation and trade execution read the cache directly — they do not go through the
`MarketDataSource`:

```python
def value_position(price_cache: PriceCache, ticker: str, quantity: float) -> float | None:
    price = price_cache.get_price(ticker)
    if price is None:
        return None  # ticker not yet priced — e.g. added this instant, first tick pending
    return price * quantity
```

A market order's fill price (PLAN.md Section 8, `POST /api/portfolio/trade`) is simply
`price_cache.get_price(ticker)` at the moment the trade handler runs — "instant fill at current
price" per PLAN.md's design, no order book to consult.

---

## 10. Testing Approach

**73 tests across 6 modules in `backend/tests/market/`, 84% overall coverage** (see
`MARKET_DATA_SUMMARY.md` for the current numbers). The approach, if reproducing from scratch:

- **`GBMSimulator` is pure and synchronous** — test it directly, no mocking of asyncio or the
  cache:
  - Seed with a fixed ticker set, call `step()` many times, assert prices stay positive (GBM's
    log-normal property should guarantee this even with an adversarial seed).
  - Assert `sigma` ordering roughly holds statistically over many steps (TSLA's realized variance
    should exceed JPM's over a large sample) — a soft check, not exact, since it's still random.
  - Assert `add_ticker`/`remove_ticker` correctly resize and rebuild the correlation matrix
    (matrix dimensions match ticker count, no stale entries).
  - Assert `_pairwise_correlation` returns the right constant for each pairing case (tech/tech,
    finance/finance, TSLA/anything, cross-sector).
- **`SimulatorDataSource`** gets thinner integration-style tests: `start()` seeds the cache
  immediately, `stop()` cancels the task cleanly, `add_ticker`/`remove_ticker` update both the
  simulator and the cache.
- **`PriceCache`** — direct unit tests: `update()` computes `previous_price`/`direction`
  correctly (including the first-ever update for a ticker), `version` increments exactly once
  per `update()` call, `get`/`get_all`/`get_price`/`remove` behave as documented, thread-safety
  isn't exercised with real concurrency (a `Lock` is trusted, not stress-tested).
- **`PriceUpdate`** — direct unit tests on the three computed properties plus `to_dict()`,
  including the `previous_price == 0` edge case for `change_percent`.
- **`MassiveDataSource`** — the `RESTClient` is mocked (`source._client` set directly in tests,
  patches target the names actually imported in `massive_client.py`); coverage here is lower
  (56%) by design since most of the module is "call the vendor SDK and handle its response,"
  which is only meaningfully testable against mocked responses, not real network calls.
- **`factory.py`** — parametrized over `MASSIVE_API_KEY` present/absent/blank, asserting the
  correct concrete type is returned in each case.

### Demo harness

A Rich terminal demo at `backend/market_data_demo.py` exercises the whole simulator path
end-to-end for manual verification:

```bash
cd backend
uv run market_data_demo.py
```

Displays a live-updating dashboard with all 10 tickers, sparklines, color-coded direction arrows,
and an event log for notable price moves. Runs 60 seconds or until Ctrl+C.

---

## 11. Extending: A Third Source

To add another provider (e.g. a different data vendor), implement `MarketDataSource`'s five
methods against a background task that writes into the same `PriceCache`:

```python
class SomeOtherDataSource(MarketDataSource):
    def __init__(self, price_cache: PriceCache, ...): ...
    async def start(self, tickers: list[str]) -> None: ...
    async def stop(self) -> None: ...
    async def add_ticker(self, ticker: str) -> None: ...
    async def remove_ticker(self, ticker: str) -> None: ...
    def get_tickers(self) -> list[str]: ...
```

Then add one branch to `create_market_data_source`:

```python
def create_market_data_source(price_cache: PriceCache) -> MarketDataSource:
    if os.environ.get("SOME_OTHER_API_KEY", "").strip():
        return SomeOtherDataSource(..., price_cache=price_cache)
    if os.environ.get("MASSIVE_API_KEY", "").strip():
        return MassiveDataSource(..., price_cache=price_cache)
    return SimulatorDataSource(price_cache=price_cache)
```

Nothing in the SSE router, portfolio code, or trade execution needs to change — that's the whole
point of the abstraction. Follow the same internal split used by both existing sources: keep any
pure "fetch/compute a price" logic separate from the thin async adapter that owns the
`asyncio.Task` and talks to `PriceCache`, so the core logic stays unit-testable without mocking
asyncio.
