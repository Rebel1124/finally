# Massive API Reference (for Real Market Data)

Research notes on the [Massive](https://massive.com) API (formerly Polygon.io, rebranded 2025-10-30)
for the pieces FinAlly needs: real-time-ish snapshot prices for a watchlist of tickers, and
end-of-day / historical bars. This grounds the design in `MARKET_INTERFACE.md`.

Existing Polygon.io API keys and the `api.polygon.io` host still work; the official SDK now
defaults to `api.massive.com`. FinAlly uses the official Python client, package name `massive`.

## Installation

```bash
uv add massive
```

Requires Python >=3.9. Repo: [massive-com/client-python](https://github.com/massive-com/client-python).

## Authentication

Every request needs an API key from the [Massive dashboard](https://massive.com/dashboard/keys).
Two equivalent ways to authenticate over raw HTTP:

- Query param: `?apiKey=YOUR_KEY`
- Header: `Authorization: Bearer YOUR_KEY`

The Python client takes the key directly and handles this for you — never build raw HTTP calls
by hand for this project:

```python
from massive import RESTClient

client = RESTClient(api_key="YOUR_KEY")  # or set POLYGON_API_KEY / pass explicitly
```

FinAlly stores the key in `MASSIVE_API_KEY` (project convention, not a client-library default —
read it explicitly with `os.environ`).

## Rate Limits

| Tier | Cost | REST limit | History | Data freshness |
|---|---|---|---|---|
| Basic (free) | $0/mo | 5 requests/min | 2 years | End-of-day only |
| Starter | $29/mo | Unlimited | 5 years | 15-minute delayed |
| Developer | $79/mo | Unlimited | 10 years | 15-minute delayed, includes trades |
| Advanced | $199/mo | Unlimited | 20+ years | Real-time, quotes, financials |

Implication for FinAlly: on the free tier, snapshot data is **not real-time** — it's whatever
the last end-of-day close was, refreshed once daily (see below). A poll interval faster than
15s buys nothing extra on this tier; it only matters once trades data / real-time is unlocked
on a paid plan.

## Endpoint 1: Full Market Snapshot (what FinAlly uses)

This is the one call that covers the whole watchlist at once — exactly what a single background
poller needs.

```
GET /v2/snapshot/locale/us/markets/stocks/tickers
```

**Query parameters:**
- `tickers` — case-sensitive comma-separated list, e.g. `AAPL,GOOGL,MSFT`. Omit to get every
  active ticker (10,000+) — always pass an explicit list for FinAlly.
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

Key fields for a price feed: `ticker`, `lastTrade.p` (price), `lastTrade.t` (nanosecond Unix
timestamp), `day` / `prevDay` for change calculations. Snapshot data resets daily at 3:30 AM ET
and repopulates from ~4:00 AM ET as exchanges report.

### Python client usage

```python
from massive import RESTClient
from massive.rest.models import SnapshotMarketType

client = RESTClient(api_key="YOUR_KEY")

snapshots = client.get_snapshot_all(
    market_type=SnapshotMarketType.STOCKS,
    tickers=["AAPL", "GOOGL", "MSFT"],
)

for snap in snapshots:
    print(snap.ticker, snap.last_trade.price, snap.last_trade.timestamp)
```

`get_snapshot_all` is synchronous (blocking network I/O) — in an asyncio app, run it via
`asyncio.to_thread(...)` rather than calling it directly on the event loop. Note `timestamp` is
Unix **nanoseconds** for `last_trade` in the raw REST payload, but the Python client's
`last_trade.timestamp` attribute is documented/observed as milliseconds — convert defensively
(divide by the right factor and sanity-check against `time.time()`) rather than assuming one
unit; FinAlly's `massive_client.py` divides by 1000 assuming milliseconds.

## Endpoint 2: Unified Snapshot (alternative, not used)

```
GET /v3/snapshot
```

Cross-asset-class snapshot (`ticker.any_of=AAPL,MSFT`, up to 250 tickers, `results[].type` is
`stocks`/`options`/`fx`/`crypto`/`indices`). More general than the stocks-only snapshot above,
but real-time data on this endpoint requires Advanced/Business plans (Starter/Developer get
15-minute-delayed here too). Not used by FinAlly — the stocks-only full-market-snapshot is
simpler and sufficient for a single-asset-class watchlist.

## Endpoint 3: Aggregate Bars (end-of-day / historical)

For historical/EOD prices — e.g. seeding a chart with real closing prices, or a future
"backtest against real data" feature.

```
GET /v2/aggs/ticker/{stocksTicker}/range/{multiplier}/{timespan}/{from}/{to}
```

- `multiplier` + `timespan` (`minute`, `hour`, `day`, `week`, `month`, `quarter`, `year`) define
  the bar size, e.g. `1/day` for daily bars.
- `from`/`to` — `YYYY-MM-DD` or millisecond timestamps.
- `adjusted` — bool, default `true` (split-adjusted).
- `sort` — `asc`/`desc`.
- `limit` — max 50,000, default 5,000.

**Response** — `results[]` array of bars: `o`, `h`, `l`, `c` (OHLC), `v` (volume),
`vw` (volume-weighted average price), `t` (Unix ms), `n` (transaction count).

### Python client usage

```python
from massive import RESTClient

client = RESTClient(api_key="YOUR_KEY")

# list_aggs paginates automatically across the full range
for bar in client.list_aggs(
    ticker="AAPL",
    multiplier=1,
    timespan="day",
    from_="2026-01-01",
    to="2026-06-30",
    adjusted=True,
    sort="asc",
    limit=50000,
):
    print(bar.timestamp, bar.open, bar.high, bar.low, bar.close, bar.volume)
```

There is no batch/multi-ticker aggregates endpoint — one call per ticker per date range. Not
currently needed by FinAlly (charts are built client-side from the SSE stream per PLAN.md
Section 10), but this is the endpoint to reach for if a future feature needs real historical
chart data instead of only what's accumulated since page load.

## Error Handling Notes

- `401` — bad/missing API key.
- `429` — rate limit exceeded (free tier: >5 req/min).
- Snapshot fields can be partially missing for illiquid tickers or just after market open
  (e.g. no `min` bar yet) — treat `lastTrade` as the only field that's safe to assume present,
  and skip/log a ticker whose snapshot is malformed rather than letting one bad ticker crash
  the whole poll cycle.

## Sources

- [massive-com/client-python](https://github.com/massive-com/client-python)
- [Massive REST API docs index](https://massive.com/docs)
- [Full Market Snapshot](https://massive.com/docs/rest/stocks/snapshots/full-market-snapshot)
- [Unified Snapshot](https://massive.com/docs/rest/stocks/snapshots/unified-snapshot)
- [Custom Bars (aggregates)](https://massive.com/docs/rest/stocks/aggregates/custom-bars)
- [Request limits FAQ](https://massive.com/knowledge-base/article/what-is-the-request-limit-for-massives-restful-apis)
- [Pricing](https://massive.com/pricing)
- [Polygon.io is Now Massive](https://massive.com/blog/polygon-is-now-massive)
- [massive on PyPI](https://pypi.org/project/massive/)
