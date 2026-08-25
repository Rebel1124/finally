"""Default seed data, inserted only when the relevant table is empty."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import UTC, datetime

DEFAULT_USER_ID = "default"
DEFAULT_CASH_BALANCE = 10000.0
DEFAULT_TICKERS = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA", "META", "JPM", "V", "NFLX"]


def seed_defaults(conn: sqlite3.Connection) -> None:
    """Seed the default user profile and watchlist if they don't already exist."""
    now = datetime.now(UTC).isoformat()

    if conn.execute("SELECT 1 FROM users_profile WHERE id = ?", (DEFAULT_USER_ID,)).fetchone() is None:
        conn.execute(
            "INSERT INTO users_profile (id, cash_balance, created_at) VALUES (?, ?, ?)",
            (DEFAULT_USER_ID, DEFAULT_CASH_BALANCE, now),
        )

    watchlist_count = conn.execute(
        "SELECT COUNT(*) FROM watchlist WHERE user_id = ?", (DEFAULT_USER_ID,)
    ).fetchone()[0]
    if watchlist_count == 0:
        conn.executemany(
            "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
            [(uuid.uuid4().hex, DEFAULT_USER_ID, ticker, now) for ticker in DEFAULT_TICKERS],
        )

    conn.commit()
