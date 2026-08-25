"""Tests for app.market.models.PriceUpdate."""

from __future__ import annotations

import dataclasses
import json
import time

import pytest

from app.market.models import PriceUpdate


def test_price_update_is_frozen():
    update = PriceUpdate(ticker="AAPL", price=100.0, previous_price=99.0, timestamp=1.0)
    with pytest.raises(dataclasses.FrozenInstanceError):
        update.price = 200.0  # type: ignore[misc]


def test_timestamp_defaults_to_now():
    before = time.time()
    update = PriceUpdate(ticker="AAPL", price=100.0, previous_price=99.0)
    after = time.time()
    assert before <= update.timestamp <= after


def test_change_positive():
    update = PriceUpdate(ticker="AAPL", price=101.5, previous_price=100.0, timestamp=1.0)
    assert update.change == 1.5


def test_change_negative():
    update = PriceUpdate(ticker="AAPL", price=98.5, previous_price=100.0, timestamp=1.0)
    assert update.change == -1.5


def test_change_rounds_to_four_decimals():
    update = PriceUpdate(ticker="AAPL", price=100.123456, previous_price=100.0, timestamp=1.0)
    assert update.change == 0.1235


def test_change_percent_computed_correctly():
    update = PriceUpdate(ticker="AAPL", price=110.0, previous_price=100.0, timestamp=1.0)
    assert update.change_percent == 10.0


def test_change_percent_zero_previous_price_returns_zero():
    update = PriceUpdate(ticker="AAPL", price=50.0, previous_price=0.0, timestamp=1.0)
    assert update.change_percent == 0.0


@pytest.mark.parametrize(
    ("price", "previous_price", "expected"),
    [
        (101.0, 100.0, "up"),
        (99.0, 100.0, "down"),
        (100.0, 100.0, "flat"),
    ],
)
def test_direction(price, previous_price, expected):
    update = PriceUpdate(ticker="AAPL", price=price, previous_price=previous_price, timestamp=1.0)
    assert update.direction == expected


def test_to_dict_contains_all_fields():
    update = PriceUpdate(ticker="AAPL", price=101.0, previous_price=100.0, timestamp=1700000000.0)
    data = update.to_dict()
    assert data == {
        "ticker": "AAPL",
        "price": 101.0,
        "previous_price": 100.0,
        "timestamp": 1700000000.0,
        "change": 1.0,
        "change_percent": 1.0,
        "direction": "up",
    }


def test_to_dict_is_json_serializable():
    update = PriceUpdate(ticker="AAPL", price=101.0, previous_price=100.0, timestamp=1700000000.0)
    # Should not raise
    json.dumps(update.to_dict())


def test_equality_of_equivalent_updates():
    a = PriceUpdate(ticker="AAPL", price=101.0, previous_price=100.0, timestamp=1.0)
    b = PriceUpdate(ticker="AAPL", price=101.0, previous_price=100.0, timestamp=1.0)
    assert a == b
