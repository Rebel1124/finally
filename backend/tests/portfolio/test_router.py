"""End-to-end tests for the portfolio HTTP routes, through the real app + lifespan."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_health_check(db):
    with TestClient(app) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_get_portfolio_returns_seed_state(db):
    with TestClient(app) as client:
        response = client.get("/api/portfolio")

    assert response.status_code == 200
    body = response.json()
    assert body["cash_balance"] == 10000.0
    assert body["positions"] == []
    assert body["total_value"] == 10000.0


def test_trade_buy_then_sell_roundtrip(db):
    with TestClient(app) as client:
        buy = client.post("/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 5, "side": "buy"})
        assert buy.status_code == 200
        body = buy.json()
        assert body["trade"]["ticker"] == "AAPL"
        assert body["trade"]["side"] == "buy"
        assert len(body["portfolio"]["positions"]) == 1

        sell = client.post("/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 5, "side": "sell"})
        assert sell.status_code == 200
        assert sell.json()["portfolio"]["positions"] == []

        history = client.get("/api/portfolio/history")
        assert history.status_code == 200
        assert len(history.json()) == 2


def test_trade_insufficient_cash_returns_400(db):
    with TestClient(app) as client:
        response = client.post(
            "/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 1_000_000, "side": "buy"}
        )
    assert response.status_code == 400
    assert response.json() == {"detail": "insufficient cash"}


def test_trade_unknown_ticker_returns_400(db):
    with TestClient(app) as client:
        response = client.post("/api/portfolio/trade", json={"ticker": "ZZZZ", "quantity": 1, "side": "buy"})
    assert response.status_code == 400
    assert response.json() == {"detail": "unknown ticker"}
