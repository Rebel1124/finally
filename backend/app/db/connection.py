"""SQLite connection helper.

Connection-per-call: each repository function opens a short-lived connection via
get_connection(), does its work, and closes it. This avoids shared mutable state
and cross-thread sqlite3.Connection issues without needing an explicit lock —
appropriate for a single-user, low-throughput app.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .. import config


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    """Open a new connection to the SQLite database, creating its parent directory if needed."""
    path = db_path or config.DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn
