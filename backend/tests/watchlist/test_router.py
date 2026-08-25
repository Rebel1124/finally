"""End-to-end tests for the watchlist HTTP routes, through the real app + lifespan."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_get_watchlist_returns_ten_seeded_tickers(db):
    with TestClient(app) as client:
        response = client.get("/api/watchlist")

    assert response.status_code == 200
    assert len(response.json()) == 10


def test_add_new_ticker_returns_201(db):
    with TestClient(app) as client:
        response = client.post("/api/watchlist", json={"ticker": "pypl"})

    assert response.status_code == 201
    assert response.json()["ticker"] == "PYPL"


def test_add_duplicate_ticker_returns_200(db):
    with TestClient(app) as client:
        client.post("/api/watchlist", json={"ticker": "PYPL"})
        response = client.post("/api/watchlist", json={"ticker": "PYPL"})

    assert response.status_code == 200


def test_delete_ticker_returns_204(db):
    with TestClient(app) as client:
        response = client.delete("/api/watchlist/AAPL")

    assert response.status_code == 204


def test_delete_unknown_ticker_is_still_204(db):
    with TestClient(app) as client:
        response = client.delete("/api/watchlist/ZZZZ")

    assert response.status_code == 204
