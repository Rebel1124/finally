"""Repository functions for reading and writing app data.

All functions operate on the single-user row (user_id="default") per PLAN.md Section 7.
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import UTC, datetime

from .connection import get_connection

USER_ID = "default"


def _now() -> str:
    return datetime.now(UTC).isoformat()


def get_profile() -> dict:
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM users_profile WHERE id = ?", (USER_ID,)).fetchone()
        return dict(row)
    finally:
        conn.close()


def update_cash_balance(new_balance: float) -> None:
    conn = get_connection()
    try:
        conn.execute("UPDATE users_profile SET cash_balance = ? WHERE id = ?", (new_balance, USER_ID))
        conn.commit()
    finally:
        conn.close()


def list_watchlist() -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT ticker, added_at FROM watchlist WHERE user_id = ? ORDER BY added_at", (USER_ID,)
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def add_watchlist_ticker(ticker: str) -> None:
    ticker = ticker.strip().upper()
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
            (uuid.uuid4().hex, USER_ID, ticker, _now()),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    finally:
        conn.close()


def remove_watchlist_ticker(ticker: str) -> None:
    conn = get_connection()
    try:
        conn.execute("DELETE FROM watchlist WHERE user_id = ? AND ticker = ?", (USER_ID, ticker))
        conn.commit()
    finally:
        conn.close()


def get_positions() -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT ticker, quantity, avg_cost, updated_at FROM positions WHERE user_id = ? ORDER BY ticker",
            (USER_ID,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_position(ticker: str) -> dict | None:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT ticker, quantity, avg_cost, updated_at FROM positions WHERE user_id = ? AND ticker = ?",
            (USER_ID, ticker),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def upsert_position(ticker: str, quantity: float, avg_cost: float) -> None:
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT (user_id, ticker) DO UPDATE SET
                quantity = excluded.quantity,
                avg_cost = excluded.avg_cost,
                updated_at = excluded.updated_at
            """,
            (uuid.uuid4().hex, USER_ID, ticker, quantity, avg_cost, _now()),
        )
        conn.commit()
    finally:
        conn.close()


def delete_position(ticker: str) -> None:
    conn = get_connection()
    try:
        conn.execute("DELETE FROM positions WHERE user_id = ? AND ticker = ?", (USER_ID, ticker))
        conn.commit()
    finally:
        conn.close()


def insert_trade(ticker: str, side: str, quantity: float, price: float) -> dict:
    conn = get_connection()
    try:
        trade_id = uuid.uuid4().hex
        executed_at = _now()
        conn.execute(
            "INSERT INTO trades (id, user_id, ticker, side, quantity, price, executed_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (trade_id, USER_ID, ticker, side, quantity, price, executed_at),
        )
        conn.commit()
        return {
            "id": trade_id,
            "user_id": USER_ID,
            "ticker": ticker,
            "side": side,
            "quantity": quantity,
            "price": price,
            "executed_at": executed_at,
        }
    finally:
        conn.close()


def list_trades(limit: int | None = None) -> list[dict]:
    conn = get_connection()
    try:
        query = "SELECT * FROM trades WHERE user_id = ? ORDER BY executed_at DESC"
        params: tuple = (USER_ID,)
        if limit is not None:
            query += " LIMIT ?"
            params = (USER_ID, limit)
        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def insert_snapshot(total_value: float) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO portfolio_snapshots (id, user_id, total_value, recorded_at) VALUES (?, ?, ?, ?)",
            (uuid.uuid4().hex, USER_ID, total_value, _now()),
        )
        conn.commit()
    finally:
        conn.close()


def list_snapshots() -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM portfolio_snapshots WHERE user_id = ? ORDER BY recorded_at ASC", (USER_ID,)
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def insert_chat_message(role: str, content: str, actions_json: str | None = None) -> dict:
    conn = get_connection()
    try:
        message_id = uuid.uuid4().hex
        created_at = _now()
        conn.execute(
            "INSERT INTO chat_messages (id, user_id, role, content, actions, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (message_id, USER_ID, role, content, actions_json, created_at),
        )
        conn.commit()
        return {
            "id": message_id,
            "user_id": USER_ID,
            "role": role,
            "content": content,
            "actions": actions_json,
            "created_at": created_at,
        }
    finally:
        conn.close()


def list_recent_chat_messages(limit: int = 20) -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM chat_messages WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (USER_ID, limit),
        ).fetchall()
        return [dict(row) for row in reversed(rows)]
    finally:
        conn.close()
