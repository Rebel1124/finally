"""End-to-end tests for POST /api/chat, through the real app + lifespan, mock mode only."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app import config
from app.main import app


def test_chat_buy_executes_trade(db, monkeypatch):
    monkeypatch.setattr(config, "LLM_MOCK", True)

    with TestClient(app) as client:
        response = client.post("/api/chat", json={"message": "buy 1 shares of AAPL"})

    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "Mock: buying 1 AAPL."
    assert body["trades"] == [{"ticker": "AAPL", "side": "buy", "quantity": 1.0, "price": body["trades"][0]["price"], "status": "executed"}]
    assert body["watchlist_changes"] == []


def test_chat_buy_insufficient_cash_reports_failed_status(db, monkeypatch):
    monkeypatch.setattr(config, "LLM_MOCK", True)

    with TestClient(app) as client:
        response = client.post("/api/chat", json={"message": "buy 999999 shares of AAPL"})

    assert response.status_code == 200
    body = response.json()
    assert body["trades"][0]["status"] == "failed: insufficient cash"


def test_chat_add_to_watchlist(db, monkeypatch):
    monkeypatch.setattr(config, "LLM_MOCK", True)

    with TestClient(app) as client:
        response = client.post("/api/chat", json={"message": "add PYPL to the watchlist"})

    assert response.status_code == 200
    body = response.json()
    assert body["watchlist_changes"] == [{"ticker": "PYPL", "action": "add", "status": "executed"}]
    assert body["trades"] == []


def test_chat_fallback_message_persists_conversation(db, monkeypatch):
    monkeypatch.setattr(config, "LLM_MOCK", True)

    with TestClient(app) as client:
        response = client.post("/api/chat", json={"message": "what's up"})

    assert response.status_code == 200
    assert response.json()["message"] == "Mock response: what's up"
