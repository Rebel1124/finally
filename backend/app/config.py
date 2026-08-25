"""Shared application settings, loaded once from the project-root .env file."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
MASSIVE_API_KEY = os.environ.get("MASSIVE_API_KEY", "")
LLM_MOCK = os.environ.get("LLM_MOCK") == "true"
DB_PATH = Path(os.environ.get("DB_PATH", str(PROJECT_ROOT / "db" / "finally.db")))
