"""Portfolio valuation and trade execution.

Transport-agnostic: raises TradeError on invalid trades rather than an HTTP
exception, so both the REST router and the future LLM chat handler can catch
it and format the error however they need.
"""

from __future__ import annotations

from app.db import repository as db
from app.market.cache import PriceCache

_price_cache: PriceCache | None = None


class TradeError(Exception):
    """Raised when a trade cannot be executed (bad ticker, cash, or shares)."""


def init(price_cache: PriceCache) -> None:
    """Wire the shared price cache into this module. Call once at startup."""
    global _price_cache
    _price_cache = price_cache


def _cache() -> PriceCache:
    if _price_cache is None:
        raise RuntimeError("portfolio.service.init() has not been called")
    return _price_cache


def _position_view(position: dict) -> dict:
    ticker = position["ticker"]
    quantity = position["quantity"]
    avg_cost = position["avg_cost"]
    current_price = _cache().get_price(ticker) or avg_cost
    market_value = quantity * current_price
    unrealized_pnl = market_value - quantity * avg_cost
    unrealized_pnl_percent = (unrealized_pnl / (quantity * avg_cost) * 100) if avg_cost and quantity else 0.0
    return {
        "ticker": ticker,
        "quantity": quantity,
        "avg_cost": avg_cost,
        "current_price": current_price,
        "market_value": market_value,
        "unrealized_pnl": unrealized_pnl,
        "unrealized_pnl_percent": unrealized_pnl_percent,
    }


def get_portfolio() -> dict:
    """Build the current portfolio view: cash, positions with live P&L, total value."""
    cash_balance = db.get_profile()["cash_balance"]
    positions = [_position_view(p) for p in db.get_positions()]
    total_value = cash_balance + sum(p["market_value"] for p in positions)
    return {
        "cash_balance": cash_balance,
        "positions": positions,
        "total_value": total_value,
    }


def execute_trade(ticker: str, side: str, quantity: float) -> dict:
    """Execute a market order at the current cache price. Returns {trade, portfolio}.

    Raises TradeError for an unknown ticker, insufficient cash (buy), or
    insufficient shares (sell).
    """
    ticker = ticker.strip().upper()
    price = _cache().get_price(ticker)
    if price is None:
        raise TradeError("unknown ticker")

    profile = db.get_profile()
    cash_balance = profile["cash_balance"]
    position = db.get_position(ticker)

    if side == "buy":
        cost = quantity * price
        if cost > cash_balance:
            raise TradeError("insufficient cash")
        if position:
            new_quantity = position["quantity"] + quantity
            new_avg_cost = (position["quantity"] * position["avg_cost"] + quantity * price) / new_quantity
        else:
            new_quantity = quantity
            new_avg_cost = price
        db.upsert_position(ticker, new_quantity, new_avg_cost)
        db.update_cash_balance(cash_balance - cost)
    elif side == "sell":
        owned = position["quantity"] if position else 0.0
        if quantity > owned:
            raise TradeError("insufficient shares")
        proceeds = quantity * price
        remaining = owned - quantity
        if remaining == 0:
            db.delete_position(ticker)
        else:
            db.upsert_position(ticker, remaining, position["avg_cost"])
        db.update_cash_balance(cash_balance + proceeds)
    else:
        raise TradeError(f"invalid side: {side}")

    trade = db.insert_trade(ticker, side, quantity, price)
    portfolio = get_portfolio()
    db.insert_snapshot(portfolio["total_value"])

    return {
        "trade": {
            "ticker": trade["ticker"],
            "side": trade["side"],
            "quantity": trade["quantity"],
            "price": trade["price"],
            "executed_at": trade["executed_at"],
        },
        "portfolio": portfolio,
    }
