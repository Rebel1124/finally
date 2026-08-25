"""Live demo of the GBM market simulator: streams prices to the terminal.

Usage:
    uv run python scripts/demo_simulator.py [TICKER ...]

Defaults to the ten watchlist tickers from PLAN.md if none are given.
Press Ctrl+C to stop.
"""

from __future__ import annotations

import asyncio
import sys

from app.market import PriceCache, create_market_data_source

DEFAULT_TICKERS = [
    "AAPL", "GOOGL", "MSFT", "AMZN", "TSLA",
    "NVDA", "META", "JPM", "V", "NFLX",
]

GREEN = "\033[32m"
RED = "\033[31m"
DIM = "\033[90m"
BOLD = "\033[1m"
RESET = "\033[0m"
CLEAR_LINE = "\033[K"
CURSOR_UP = "\033[{n}A"
HIDE_CURSOR = "\033[?25l"
SHOW_CURSOR = "\033[?25h"

ARROWS = {"up": "▲", "down": "▼", "flat": "▬"}
COLORS = {"up": GREEN, "down": RED, "flat": DIM}

ROW_FORMAT = "{ticker:<6} {price:>10.2f}  {color}{arrow} {change:>+7.2f} ({pct:>+6.2f}%){reset}"


def render_row(ticker: str, price: float, change: float, pct: float, direction: str) -> str:
    color = COLORS[direction]
    arrow = ARROWS[direction]
    return ROW_FORMAT.format(
        ticker=ticker, price=price, color=color, arrow=arrow, change=change, pct=pct, reset=RESET
    )


async def main(tickers: list[str]) -> None:
    cache = PriceCache()
    source = create_market_data_source(cache)
    await source.start(tickers)

    header = f"{BOLD}{'TICKER':<6} {'PRICE':>10}   {'CHANGE':>16}{RESET}"
    print(f"Streaming {len(tickers)} tickers (Ctrl+C to stop)\n")
    print(header)
    for _ in tickers:
        print()

    try:
        sys.stdout.write(HIDE_CURSOR)
        while True:
            await asyncio.sleep(0.5)
            sys.stdout.write(CURSOR_UP.format(n=len(tickers)))
            for ticker in tickers:
                update = cache.get(ticker)
                line = (
                    render_row(ticker, update.price, update.change, update.change_percent, update.direction)
                    if update is not None
                    else f"{ticker:<6} {DIM}waiting...{RESET}"
                )
                sys.stdout.write(f"\r{CLEAR_LINE}{line}\n")
            sys.stdout.flush()
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        await source.stop()
        sys.stdout.write(SHOW_CURSOR)
        print("\nStopped.")


if __name__ == "__main__":
    tickers = sys.argv[1:] or DEFAULT_TICKERS
    asyncio.run(main(tickers))
