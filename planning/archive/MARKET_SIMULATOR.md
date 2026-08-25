# Market Simulator Design

Design for the default (no-API-key) price feed: a Geometric Brownian Motion simulator producing
correlated, realistic-looking price ticks for the watchlist. Implemented in
`backend/app/market/simulator.py` and `backend/app/market/seed_prices.py` — this document
describes the approach and math; treat the source as ground truth if they diverge.

## Why GBM

Geometric Brownian Motion is the standard model behind Black-Scholes and most retail-facing
price simulators: prices are log-normally distributed (never go negative), moves compound
multiplicatively, and two parameters per ticker — drift (`mu`) and volatility (`sigma`) — are
enough to make a stock "feel" like itself (TSLA choppier than JPM, etc.) without hand-authoring
per-tick behavior.

```
S(t+dt) = S(t) * exp((mu - sigma^2/2) * dt + sigma * sqrt(dt) * Z)
```

- `S(t)` — current price
- `mu` — annualized drift (expected return)
- `sigma` — annualized volatility
- `dt` — time step, expressed as a fraction of a trading year
- `Z` — a standard normal random draw (correlated across tickers — see below)

The `- sigma^2/2` term is the standard Itô correction so that `mu` remains the actual expected
*arithmetic* return despite the log-normal compounding.

## Time Step

The simulator ticks every 500ms (matching the SSE cadence in PLAN.md Section 6), so `dt` is
500ms expressed as a fraction of a 252-day, 6.5-hour trading year:

```python
TRADING_SECONDS_PER_YEAR = 252 * 6.5 * 3600  # 5,896,800
DEFAULT_DT = 0.5 / TRADING_SECONDS_PER_YEAR   # ≈ 8.48e-8
```

At this `dt`, each individual tick moves a price by a fraction of a cent on average — prices
drift smoothly and continuously rather than jumping, which is what makes the sparklines and
flash animations look natural instead of jittery.

## Correlated Moves

Real markets don't move ticker-by-ticker independently — tech stocks tend to move together, so
should this simulation. Each tick draws one independent standard-normal vector (one value per
ticker), then applies a Cholesky decomposition of a correlation matrix to turn it into a
correlated vector:

```python
z_independent = np.random.standard_normal(n)
z_correlated = cholesky_matrix @ z_independent
```

**Correlation structure**, sector-based, hardcoded per pairing rule (see `seed_prices.py`):

| Pairing | Correlation |
|---|---|
| Two tech tickers (AAPL, GOOGL, MSFT, AMZN, META, NVDA, NFLX) | 0.6 |
| Two finance tickers (JPM, V) | 0.5 |
| Either side is TSLA | 0.3 (TSLA "does its own thing") |
| Cross-sector, or either ticker unrecognized | 0.3 |

The Cholesky matrix is rebuilt whenever a ticker is added or removed (watchlist changes are
infrequent — O(n²) rebuild on a <50-ticker list is negligible) and reused across every tick in
between (the hot path — `step()` — must stay cheap, since it runs twice a second).

## Per-Ticker Parameters

Seed prices and `(mu, sigma)` live in one static table, `seed_prices.py`, so tuning "how wiggly
does TSLA feel" is a one-line data change, not a code change:

| Ticker | Seed price | sigma (volatility) | mu (drift) | Character |
|---|---|---|---|---|
| AAPL | $190 | 0.22 | 0.05 | steady |
| GOOGL | $175 | 0.25 | 0.05 | steady |
| MSFT | $420 | 0.20 | 0.05 | steady |
| AMZN | $185 | 0.28 | 0.05 | moderate |
| TSLA | $250 | 0.50 | 0.03 | high volatility |
| NVDA | $800 | 0.40 | 0.08 | high volatility, strong drift |
| META | $500 | 0.30 | 0.05 | moderate |
| JPM | $195 | 0.18 | 0.04 | low volatility (bank) |
| V | $280 | 0.17 | 0.04 | low volatility (payments) |
| NFLX | $600 | 0.35 | 0.05 | moderate-high |

A ticker added at runtime that isn't in this table (e.g. user adds an arbitrary symbol via chat
or the watchlist UI) falls back to a random seed price in `[50, 300]` and default params
`{sigma: 0.25, mu: 0.05}` — the goal is "looks plausible," not "matches the real security."

## Random Events

On top of the continuous GBM drift, each ticker has a small independent chance per tick of a
sudden jump — for visual drama, so the demo doesn't feel purely like slow drift:

```python
event_probability = 0.001  # 0.1% per tick per ticker
if random.random() < event_probability:
    shock_magnitude = random.uniform(0.02, 0.05)   # 2-5%
    shock_sign = random.choice([-1, 1])
    price *= 1 + shock_magnitude * shock_sign
```

With 10 tickers ticking twice a second, that's roughly one shock event somewhere in the
watchlist every ~50 seconds — frequent enough to be noticeable in a live demo, rare enough not
to feel gimmicky.

## Code Structure

```python
class GBMSimulator:
    """Pure simulation math — no async, no I/O, no cache access."""
    def step(self) -> dict[str, float]: ...          # advance one tick, all tickers
    def add_ticker(self, ticker: str) -> None: ...    # rebuilds Cholesky
    def remove_ticker(self, ticker: str) -> None: ...  # rebuilds Cholesky
    def get_price(self, ticker: str) -> float | None: ...
    def get_tickers(self) -> list[str]: ...

class SimulatorDataSource(MarketDataSource):
    """Async wrapper: owns the background task, writes GBMSimulator output into PriceCache."""
    async def start(self, tickers: list[str]) -> None: ...
    async def stop(self) -> None: ...
    async def add_ticker(self, ticker: str) -> None: ...
    async def remove_ticker(self, ticker: str) -> None: ...
    def get_tickers(self) -> list[str]: ...
```

Deliberate split: `GBMSimulator` is synchronous, dependency-free math (easy to unit test —
seed it, call `step()`, assert on the distribution of outputs, no event loop or mocking needed).
`SimulatorDataSource` is the thin async adapter that satisfies `MarketDataSource` and is the only
piece that touches `asyncio` or the `PriceCache`. This mirrors the `MassiveDataSource` split
described in `MARKET_INTERFACE.md` — both concrete sources separate "produce a price" from
"run on a schedule and publish it" — so the two implementations stay structurally symmetric even
though one computes prices and the other fetches them.

### `SimulatorDataSource._run_loop`

```python
async def _run_loop(self) -> None:
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
tick (e.g. a transient numpy issue) shouldn't take down price streaming for the rest of the
session; the loop just tries again 500ms later.

## Testing Approach

Because `GBMSimulator` is pure and synchronous, it's tested directly without mocking asyncio or
the cache:

- Seed with a fixed ticker set, call `step()` many times, assert prices stay positive (GBM's
  log-normal property should guarantee this even with an adversarial seed).
- Assert `sigma` ordering roughly holds statistically over many steps (TSLA's realized variance
  should exceed JPM's over a large sample) — a soft check, not exact, since it's still random.
- Assert `add_ticker`/`remove_ticker` correctly resize and rebuild the correlation matrix (matrix
  dimensions match ticker count, no stale entries).
- Assert the correlation-grouping rule (`_pairwise_correlation`) returns the right constant for
  each pairing case in the table above.

`SimulatorDataSource` gets thinner integration-style tests: `start()` seeds the cache
immediately, `stop()` cancels the task cleanly, `add_ticker`/`remove_ticker` update both the
simulator and the cache.

## Non-Goals

- **Not a market microstructure simulator.** No order book, no bid/ask spread modeling, no
  volume simulation feeding into price impact. FinAlly only needs a plausible last-trade price
  per tick, per PLAN.md's "market orders only, instant fill" design.
- **Not calibrated to real historical volatility.** `sigma`/`mu` values are chosen to *feel*
  right in a live demo (distinguishable ticker personalities), not fit from real return series.
