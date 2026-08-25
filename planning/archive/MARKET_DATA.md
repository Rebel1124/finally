# Market Data Backend — Review

Independent review of `backend/app/market/` against `PLAN.md` Section 6, `MARKET_INTERFACE.md`,
`MARKET_SIMULATOR.md`, and `MASSIVE_API.md`. Covers architecture, code correctness, and the test
suite.

## Status: all findings fixed and verified

Every finding below has been fixed, the fix verified with tests, and the full suite re-run clean.

```
uv run --extra dev pytest -v          → 83 passed, 0 failed (~1.3s)
uv run --extra dev pytest --cov=app   → 97% overall
uv run --extra dev ruff check app/ tests/ → All checks passed
```

| Module | Coverage |
|---|---|
| `models.py` | 100% |
| `cache.py` | 100% |
| `interface.py` | 100% |
| `factory.py` | 100% |
| `simulator.py` | 98% |
| `massive_client.py` | 94% |
| `stream.py` | 92% |
| **Total** | **97%** |

## Findings and fixes

### 1. Critical — `MassiveDataSource` read a timestamp attribute that doesn't exist on the installed SDK — FIXED

`massive_client.py` read `snap.last_trade.timestamp`, but the installed `massive` client (v2.2.0,
resolved from the project's own `>=1.0.0` constraint) has no `.timestamp` attribute on
`LastTrade` — verified directly against the installed package:

```
$ uv run python3 -c "from massive.rest.models.snapshot import LastTrade; \
    lt = LastTrade.from_dict({'T':'AAPL','t':1707580800000000000,'p':190.5}); \
    print(lt.timestamp)"
AttributeError: 'LastTrade' object has no attribute 'timestamp'
```

`LastTrade` is a plain dataclass-backed model with `sip_timestamp` (nanoseconds, populated from
the raw payload's `t` field), `participant_timestamp`, and `trf_timestamp` — but no `timestamp`.
Every real snapshot would hit this `AttributeError`, which is silently swallowed by the existing
per-snapshot `except (AttributeError, TypeError)` handler: **with a real `MASSIVE_API_KEY`
configured, the poller would run, log nothing alarming, and update zero tickers, forever.** The
mocked test suite didn't catch it because `unittest.mock.MagicMock()` accepts and returns any
attribute assigned to it, so the mock was shaped to match the code under test rather than the
real SDK.

**Fix applied** (`massive_client.py`):

```python
price = snap.last_trade.price
# sip_timestamp is Unix nanoseconds → convert to seconds
timestamp = snap.last_trade.sip_timestamp / 1_000_000_000.0
```

Also fixed:
- `MASSIVE_API.md`'s note about `.timestamp` being "documented/observed as milliseconds" — that
  claim doesn't hold against the installed SDK; corrected to describe `sip_timestamp` in
  nanoseconds.
- `tests/market/test_massive.py`'s mocks now set `sip_timestamp` (not `timestamp`), and a new
  test, `test_poll_updates_cache_using_real_sdk_models`, builds a real
  `massive.rest.models.snapshot.TickerSnapshot` via `TickerSnapshot.from_dict(...)` instead of a
  `MagicMock`, so a future SDK field rename can't hide behind a mock again.

### 2. High — SSE stream endpoint had no dedicated tests — FIXED

`stream.py` (`create_stream_router` / `_generate_events`) had 33% coverage from incidental
import-time execution only, and no `test_stream.py` existed.

**Fix applied**: added `tests/market/test_stream.py` (9 tests), driving `_generate_events`
directly with a minimal fake `Request` (controls disconnect timing without real sleeps) plus two
tests on `create_stream_router` itself (route path/method registration). Covers:
- the `retry: 1000` directive clients need for auto-reconnect
- immediate stop on client disconnect
- no `data:` frame when the cache is empty
- one `data:` frame containing every tracked ticker when the cache has data
- version-based change detection: unchanged version → no resend; version bump → new frame

`stream.py` coverage is now 92%. The remaining uncovered lines are the actual `StreamingResponse`
route-handler body (`stream_prices`) and the `CancelledError` log line — reaching those needs a
real ASGI request. I tried adding an `httpx.ASGITransport` + `AsyncClient` integration test for
this; it reliably hung (5s timeout, every run) because that transport doesn't stream `StreamingResponse`
output incrementally for an endpoint that never terminates on its own. Given the endpoint body is
a 4-line pass-through to `StreamingResponse(...)` and all its actual logic lives in
`_generate_events` (now fully covered), I judged a fragile, hang-prone dependency not worth adding
for that remaining wrapper — reverted the `httpx` dev-dependency addition.

### 3. Medium — ticker case normalization differed between the two `MarketDataSource` implementations — FIXED

`MassiveDataSource.add_ticker` normalized (`.upper().strip()`); `SimulatorDataSource`/
`GBMSimulator` didn't, so adding `"aapl"` under the simulator would have created a separate cache
entry from an existing `"AAPL"` one, breaking `MARKET_INTERFACE.md`'s "downstream code never
knows or cares which one is active" contract.

**Fix applied** (`simulator.py`): `GBMSimulator.add_ticker`/`remove_ticker`/`get_price` and
`_add_ticker_internal` (the single entry point used by both batch `__init__` and `add_ticker`)
now normalize with `.upper().strip()`. `SimulatorDataSource.add_ticker`/`remove_ticker`/`start`
normalize before touching both the simulator and the cache, so the two never disagree on a
ticker's canonical key.

### 4. Low — deprecated event loop policy fixture fired a warning on every test — FIXED

`tests/conftest.py` defined an `event_loop_policy` fixture returning
`asyncio.DefaultEventLoopPolicy()`, deprecated as of Python 3.14 and slated for removal in 3.16.
It wasn't doing anything `pytest-asyncio`'s `asyncio_mode = "auto"` doesn't already provide.

**Fix applied**: removed the fixture. `conftest.py` is now just the module docstring. Full suite
reruns with zero warnings.

### 5. Low — redundant double-rounding of prices — FIXED

`GBMSimulator.step()` rounded each price to 2 decimals before returning it, and
`PriceCache.update()` rounded again on the way in. The simulator's *internal* running price state
(`self._prices[ticker]`) was never rounded either way — only the returned `dict` value was — so
this was a pointless extra `round()` call with no effect once the cache also rounds.

**Fix applied**: `step()` now returns `self._prices[ticker]` directly; `PriceCache.update()` is
the single place rounding happens. `test_simulator.py`'s
`test_prices_rounded_to_two_decimals` (which tested the now-removed behavior) was replaced with
`test_step_result_matches_internal_state`, confirming `step()`'s return value and `get_price()`
agree; cache-level rounding remains covered by `test_cache.py::test_price_rounding`.

## What's solid (unchanged from first pass)

- Architecture matches the design docs exactly: `MarketDataSource` ABC, `PriceCache` with a
  version counter, factory keyed on `MASSIVE_API_KEY.strip()`.
- GBM math matches `MARKET_SIMULATOR.md`'s formula, `dt`, and correlation table exactly.
- `PriceCache` is fully covered and correctly thread-safe.
- Error isolation in both sources is well-designed in shape: a bad tick/snapshot is caught,
  logged, and skipped rather than killing the background task.
- No secrets in the repo; `.env` is gitignored and was never committed.

## Recommended order of fixes

All five items above are complete. No outstanding market-data work from this review.
