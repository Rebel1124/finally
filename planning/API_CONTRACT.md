# API Contract (authoritative for this build)

This resolves exact request/response shapes for PLAN.md Section 8. Frontend, Backend API,
and LLM engineers must all conform to this document. If a change is needed, update this
file first, then update code.

All endpoints are same-origin (`/api/*`). JSON in, JSON out, except the SSE stream.

## System

`GET /api/health` -> `200 {"status": "ok"}`

## Market data stream

`GET /api/stream/prices` — already implemented in `backend/app/market/stream.py`. SSE.
Each event: `data: {"AAPL": {"ticker": "AAPL", "price": 190.5, "previous_price": 189.9, "timestamp": 1234.5, "change": 0.6, "change_percent": 0.32, "direction": "up"}, "GOOGL": {...}, ...}\n\n`
— one JSON object keyed by ticker, containing ALL currently tracked tickers, sent whenever
the price cache version changes (roughly every 500ms if anything moved). Not per-ticker events.

## Watchlist

`GET /api/watchlist` -> `200`
```json
[
  {"ticker": "AAPL", "price": 190.5, "previous_price": 189.9, "change": 0.6, "change_percent": 0.32, "direction": "up", "added_at": "2026-08-25T12:00:00Z"}
]
```
If a ticker has no price yet in the cache (just added, source hasn't ticked), `price`,
`previous_price`, `change`, `change_percent`, `direction` are `null`.

`POST /api/watchlist` body `{"ticker": "PYPL"}` -> `201` same single-object shape as above.
Ticker is upper-cased and stripped server-side. Duplicate add is a no-op `200` (not an error).

`DELETE /api/watchlist/{ticker}` -> `204` no body. Removing an unknown ticker is also `204`
(idempotent delete, not an error).

## Portfolio

`GET /api/portfolio` -> `200`
```json
{
  "cash_balance": 8000.0,
  "positions": [
    {
      "ticker": "AAPL", "quantity": 10, "avg_cost": 185.0,
      "current_price": 190.5, "market_value": 1905.0,
      "unrealized_pnl": 55.0, "unrealized_pnl_percent": 2.97
    }
  ],
  "total_value": 9905.0
}
```
`total_value` = `cash_balance` + sum of `market_value`. If a position's ticker has no price
in the cache, `current_price` falls back to `avg_cost` (so P&L reads 0 rather than crashing).

`POST /api/portfolio/trade` body `{"ticker": "AAPL", "quantity": 10, "side": "buy"}` -> `200`
```json
{
  "trade": {"ticker": "AAPL", "side": "buy", "quantity": 10, "price": 190.5, "executed_at": "2026-08-25T12:00:00Z"},
  "portfolio": { /* same shape as GET /api/portfolio */ }
}
```
Fills instantly at the current cache price for the ticker. Errors: `400` with
`{"detail": "insufficient cash"}`, `{"detail": "insufficient shares"}`, or
`{"detail": "unknown ticker"}` (no price available). `side` is `"buy"` or `"sell"`.
Buying an unheld ticker creates a position; selling all shares of a position deletes it.
`avg_cost` on a buy is the weighted average of existing + new shares; a sell does not change
`avg_cost` of the remaining shares.

Every successful trade also appends a row to `portfolio_snapshots` (recorded immediately,
in addition to the 30s background snapshot task).

`GET /api/portfolio/history` -> `200`
```json
[
  {"total_value": 10000.0, "recorded_at": "2026-08-25T12:00:00Z"}
]
```
Ordered oldest to newest.

## Chat

`POST /api/chat` body `{"message": "buy 10 shares of apple"}` -> `200`
```json
{
  "message": "Bought 10 shares of AAPL at $190.50.",
  "trades": [{"ticker": "AAPL", "side": "buy", "quantity": 10, "price": 190.5, "status": "executed"}],
  "watchlist_changes": [{"ticker": "PYPL", "action": "add", "status": "executed"}]
}
```
`trades` and `watchlist_changes` are always present as arrays (possibly empty). Each item has
a `status` of `"executed"` or `"failed: <reason>"` — a failed trade/watchlist change does not
fail the whole request; the LLM's `message` should explain the failure to the user.
Trades and watchlist changes execute through the same service functions as the manual REST
endpoints above (`POST /api/portfolio/trade`, `POST /api/watchlist`) — not duplicated logic.

### `LLM_MOCK=true` deterministic behavior

When `LLM_MOCK` is true, `POST /api/chat` never calls OpenRouter. Instead it parses `message`
with simple case-insensitive regexes so E2E tests get deterministic, controllable behavior:

- `buy N TICKER` (optionally "shares of") -> `trades: [{"ticker": TICKER_UPPER, "side": "buy", "quantity": N}]`, reply message `"Mock: buying N TICKER."`
- `sell N TICKER` -> same, `side: "sell"`, reply `"Mock: selling N TICKER."`
- `add TICKER to watchlist` (optionally "the") -> `watchlist_changes: [{"ticker": TICKER_UPPER, "action": "add"}]`, reply `"Mock: adding TICKER to watchlist."`
- `remove TICKER from watchlist` -> same, `action: "remove"`, reply `"Mock: removing TICKER from watchlist."`
- Anything else -> `trades: []`, `watchlist_changes: []`, reply `"Mock response: <original message>"`.

Every parsed trade/watchlist action still goes through the real service-layer validation
(`execute_trade`, `add_to_watchlist`, `remove_from_watchlist`) — mock mode only replaces the
LLM call, not the execution/validation logic. So `buy 999999 AAPL` in mock mode still fails
with `"failed: insufficient cash"` in the `trades[].status` field, same as it would with a real
LLM response.

## Shared error shape

Any `4xx` from any endpoint: `{"detail": "human readable reason"}` (FastAPI default via
`HTTPException`).
