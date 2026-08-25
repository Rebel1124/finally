# FinAlly Backend

FastAPI (Python/`uv`) backend for the FinAlly AI trading workstation. See
[`../planning/PLAN.md`](../planning/PLAN.md) for the full project specification and
[`../planning/MARKET_DATA_DESIGN.md`](../planning/MARKET_DATA_DESIGN.md) for the design of the
market data subsystem implemented here.

## Status

The market data subsystem (`app/market/`) is implemented and tested: the unified
`MarketDataSource` interface, the GBM price simulator, and the Massive (Polygon.io) REST client.
The rest of the backend (database, portfolio, chat, HTTP app) is not yet built.

## Setup

```bash
cd backend
uv sync --extra dev
```

## Running tests

```bash
uv run --extra dev pytest -v
uv run --extra dev pytest --cov=app --cov-report=term-missing
```

## Package layout

```
app/
  market/
    models.py         # PriceUpdate — immutable price snapshot
    cache.py           # PriceCache — thread-safe in-memory price store
    interface.py        # MarketDataSource — abstract contract
    seed_prices.py       # Seed prices, GBM params, correlation groups
    simulator.py          # GBMSimulator + SimulatorDataSource
    massive_client.py      # MassiveDataSource (Massive/Polygon.io REST poller)
    factory.py               # create_market_data_source()
    stream.py                 # SSE endpoint factory
tests/
  market/                     # Unit tests for the above
```

## Usage

```python
from app.market import PriceCache, create_market_data_source

cache = PriceCache()
source = create_market_data_source(cache)  # simulator, or Massive if MASSIVE_API_KEY is set
await source.start(["AAPL", "GOOGL", "MSFT"])

price = cache.get_price("AAPL")
```
