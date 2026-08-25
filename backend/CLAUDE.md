# Backend — Agent Notes

This is a `uv`-managed FastAPI Python project. See [`../planning/PLAN.md`](../planning/PLAN.md)
for the full specification and [`../planning/MARKET_DATA_DESIGN.md`](../planning/MARKET_DATA_DESIGN.md)
for the market data subsystem design.

## Commands

```bash
uv sync --extra dev             # install dependencies
uv run --extra dev pytest -v    # run tests
```

## Current state

`app/market/` — market data subsystem (unified `MarketDataSource` interface, GBM simulator,
Massive API client, SSE stream) — implemented, see `tests/market/` for coverage.

Not yet built: SQLite database layer, portfolio/trade endpoints, watchlist endpoints, LLM chat
integration, `app/main.py` FastAPI app wiring it all together. See PLAN.md sections 7-9 for specs.
