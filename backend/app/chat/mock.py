"""Deterministic regex-based mock LLM responses, used when config.LLM_MOCK is true."""

from __future__ import annotations

import re

from .schemas import LLMResponse, TradeAction, WatchlistChange

_BUY_RE = re.compile(r"buy (\d+(?:\.\d+)?) (?:shares of )?(\w+)", re.IGNORECASE)
_SELL_RE = re.compile(r"sell (\d+(?:\.\d+)?) (?:shares of )?(\w+)", re.IGNORECASE)
_ADD_RE = re.compile(r"add (?:the )?(\w+) to (?:the )?watchlist", re.IGNORECASE)
_REMOVE_RE = re.compile(r"remove (?:the )?(\w+) from (?:the )?watchlist", re.IGNORECASE)


def get_mock_response(message: str) -> LLMResponse:
    if match := _BUY_RE.search(message):
        quantity, ticker = float(match.group(1)), match.group(2).upper()
        return LLMResponse(
            message=f"Mock: buying {match.group(1)} {ticker}.",
            trades=[TradeAction(ticker=ticker, side="buy", quantity=quantity)],
        )

    if match := _SELL_RE.search(message):
        quantity, ticker = float(match.group(1)), match.group(2).upper()
        return LLMResponse(
            message=f"Mock: selling {match.group(1)} {ticker}.",
            trades=[TradeAction(ticker=ticker, side="sell", quantity=quantity)],
        )

    if match := _ADD_RE.search(message):
        ticker = match.group(1).upper()
        return LLMResponse(
            message=f"Mock: adding {ticker} to watchlist.",
            watchlist_changes=[WatchlistChange(ticker=ticker, action="add")],
        )

    if match := _REMOVE_RE.search(message):
        ticker = match.group(1).upper()
        return LLMResponse(
            message=f"Mock: removing {ticker} from watchlist.",
            watchlist_changes=[WatchlistChange(ticker=ticker, action="remove")],
        )

    return LLMResponse(message=f"Mock response: {message}")
