"""Builds the system prompt and portfolio/watchlist context for the LLM."""

from __future__ import annotations

from app.portfolio import service as portfolio_service
from app.watchlist import service as watchlist_service

SYSTEM_PROMPT = """You are FinAlly, an AI trading assistant embedded in a simulated trading terminal.

You can see the user's current portfolio and watchlist below. Your job:
- Analyze portfolio composition, risk concentration, and P&L when asked or relevant.
- Suggest trades with clear reasoning.
- Execute trades when the user asks for one or agrees to a suggestion you made.
- Manage the watchlist proactively (add tickers the user is discussing, remove ones they're done with).
- Be concise and data-driven. No filler.

The portfolio and watchlist data below is the live, authoritative state as of this exact
message. For any question about cash, positions, P&L, or total value, always use these
exact current figures — never reuse or extrapolate from numbers you or the user mentioned
earlier in this conversation, since trades executed since then make old figures stale.

The "Cash balance" figure below is already final and fully up to date — it already accounts
for every trade ever executed, including any positions currently held. Never recompute it
(e.g. by subtracting a position's cost from it, or re-applying a trade's cost) — doing so
double-counts and produces a wrong number. When asked about cash, copy the "Cash balance"
figure directly with no arithmetic. The same applies to "Total portfolio value": use it as
given, never re-derive it yourself.

Always respond with valid JSON matching this schema:
{"message": str, "trades": [{"ticker": str, "side": "buy"|"sell", "quantity": number}], "watchlist_changes": [{"ticker": str, "action": "add"|"remove"}]}

trades and watchlist_changes are optional and default to empty lists. Only include a trade or
watchlist change if the user asked for it or explicitly agreed to your suggestion."""


def build_portfolio_context() -> str:
    """Render current cash, positions, watchlist, and total value as readable text for the prompt."""
    portfolio = portfolio_service.get_portfolio()
    watchlist = watchlist_service.get_watchlist()

    lines = [f"Cash balance: ${portfolio['cash_balance']:.2f}"]

    if portfolio["positions"]:
        lines.append("Positions:")
        for p in portfolio["positions"]:
            lines.append(
                f"  {p['ticker']}: {p['quantity']} shares @ avg cost ${p['avg_cost']:.2f}, "
                f"current price ${p['current_price']:.2f}, "
                f"unrealized P&L ${p['unrealized_pnl']:.2f} ({p['unrealized_pnl_percent']:.2f}%)"
            )
    else:
        lines.append("Positions: none")

    if watchlist:
        lines.append("Watchlist:")
        for w in watchlist:
            price = f"${w['price']:.2f}" if w["price"] is not None else "no price yet"
            lines.append(f"  {w['ticker']}: {price}")
    else:
        lines.append("Watchlist: empty")

    lines.append(f"Total portfolio value: ${portfolio['total_value']:.2f}")

    return "\n".join(lines)
