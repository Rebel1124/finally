"""Watchlist management: DB rows joined with live prices, kept in sync with
the market data source's active ticker set.
"""

from __future__ import annotations

from app.db import repository as db
from app.market.cache import PriceCache
from app.market.interface import MarketDataSource

_price_cache: PriceCache | None = None
_market_source: MarketDataSource | None = None


def init(price_cache: PriceCache, market_source: MarketDataSource) -> None:
    """Wire the shared price cache and market data source into this module."""
    global _price_cache, _market_source
    _price_cache = price_cache
    _market_source = market_source


def _cache() -> PriceCache:
    if _price_cache is None:
        raise RuntimeError("watchlist.service.init() has not been called")
    return _price_cache


def _source() -> MarketDataSource:
    if _market_source is None:
        raise RuntimeError("watchlist.service.init() has not been called")
    return _market_source


def _entry_view(ticker: str, added_at: str) -> dict:
    update = _cache().get(ticker)
    price_fields = (
        {
            "price": update.price,
            "previous_price": update.previous_price,
            "change": update.change,
            "change_percent": update.change_percent,
            "direction": update.direction,
        }
        if update
        else {"price": None, "previous_price": None, "change": None, "change_percent": None, "direction": None}
    )
    return {"ticker": ticker, "added_at": added_at, **price_fields}


def get_watchlist() -> list[dict]:
    """Current watchlist tickers joined with their latest cached price."""
    return [_entry_view(row["ticker"], row["added_at"]) for row in db.list_watchlist()]


async def add_to_watchlist(ticker: str) -> dict:
    """Add a ticker to the watchlist and start tracking it in the market source."""
    ticker = ticker.strip().upper()
    db.add_watchlist_ticker(ticker)
    await _source().add_ticker(ticker)
    row = next(r for r in db.list_watchlist() if r["ticker"] == ticker)
    return _entry_view(row["ticker"], row["added_at"])


async def remove_from_watchlist(ticker: str) -> None:
    """Remove a ticker from the watchlist, the market source, and the price cache."""
    ticker = ticker.strip().upper()
    db.remove_watchlist_ticker(ticker)
    await _source().remove_ticker(ticker)
    _cache().remove(ticker)
