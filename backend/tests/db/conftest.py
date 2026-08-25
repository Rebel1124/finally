"""Shared fixtures for app.db tests."""

from __future__ import annotations

import pytest

from app import config
from app.db import init_db


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    """Point config.DB_PATH at a fresh temp file for the duration of a test."""
    path = tmp_path / "test.db"
    monkeypatch.setattr(config, "DB_PATH", path)
    return path


@pytest.fixture
def db(db_path):
    """A freshly initialized (schema created + seeded) temp database."""
    init_db()
    return db_path
