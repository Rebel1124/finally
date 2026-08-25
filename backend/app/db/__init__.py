"""SQLite database layer: connection, schema, seeding, and repository functions."""

from __future__ import annotations

from .connection import get_connection
from .schema import create_schema
from .seed import seed_defaults


def init_db() -> None:
    """Create tables if missing and seed default data if empty. Safe to call on every startup."""
    conn = get_connection()
    try:
        create_schema(conn)
        seed_defaults(conn)
    finally:
        conn.close()
