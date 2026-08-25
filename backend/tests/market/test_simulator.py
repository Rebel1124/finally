"""Tests for app.market.simulator.GBMSimulator (pure math, no asyncio)."""

from __future__ import annotations

import random

import numpy as np
import pytest

from app.market.seed_prices import (
    CROSS_GROUP_CORR,
    DEFAULT_PARAMS,
    INTRA_FINANCE_CORR,
    INTRA_TECH_CORR,
    SEED_PRICES,
    TSLA_CORR,
)
from app.market.simulator import GBMSimulator


@pytest.fixture(autouse=True)
def _seeded_random():
    """Deterministic randomness for reproducible statistical assertions."""
    np.random.seed(42)

    random.seed(42)


def test_init_seeds_known_tickers_with_seed_prices():
    sim = GBMSimulator(tickers=["AAPL", "GOOGL"])
    assert sim.get_price("AAPL") == SEED_PRICES["AAPL"]
    assert sim.get_price("GOOGL") == SEED_PRICES["GOOGL"]


def test_init_seeds_unknown_ticker_with_random_price_in_range():
    sim = GBMSimulator(tickers=["ZZZZ"])
    price = sim.get_price("ZZZZ")
    assert price is not None
    assert 50.0 <= price <= 300.0


def test_get_tickers_returns_all_initialized_tickers():
    sim = GBMSimulator(tickers=["AAPL", "GOOGL", "MSFT"])
    assert sim.get_tickers() == ["AAPL", "GOOGL", "MSFT"]


def test_get_price_unknown_ticker_returns_none():
    sim = GBMSimulator(tickers=["AAPL"])
    assert sim.get_price("NOPE") is None


def test_step_with_no_tickers_returns_empty_dict():
    sim = GBMSimulator(tickers=[])
    assert sim.step() == {}


def test_step_returns_price_for_every_ticker():
    sim = GBMSimulator(tickers=["AAPL", "GOOGL", "MSFT"])
    result = sim.step()
    assert set(result.keys()) == {"AAPL", "GOOGL", "MSFT"}


def test_step_prices_stay_positive_over_many_ticks():
    sim = GBMSimulator(tickers=list(SEED_PRICES.keys()))
    for _ in range(2000):
        prices = sim.step()
        assert all(p > 0 for p in prices.values())


def test_step_updates_internal_price_state():
    sim = GBMSimulator(tickers=["AAPL"])
    first = sim.step()
    assert sim.get_price("AAPL") == first["AAPL"]


def test_step_prices_rounded_to_two_decimals():
    sim = GBMSimulator(tickers=["AAPL", "TSLA"])
    result = sim.step()
    for price in result.values():
        assert price == round(price, 2)


def test_higher_sigma_ticker_has_higher_realized_variance():
    """TSLA (sigma=0.50) should be more volatile than JPM (sigma=0.18) over a large sample."""
    sim = GBMSimulator(tickers=["TSLA", "JPM"], event_probability=0.0)
    tsla_prices = []
    jpm_prices = []
    for _ in range(5000):
        result = sim.step()
        tsla_prices.append(result["TSLA"])
        jpm_prices.append(result["JPM"])

    tsla_returns = np.diff(np.log(tsla_prices))
    jpm_returns = np.diff(np.log(jpm_prices))
    assert np.std(tsla_returns) > np.std(jpm_returns)


def test_add_ticker_adds_new_ticker_with_seed_price():
    sim = GBMSimulator(tickers=["AAPL"])
    sim.add_ticker("GOOGL")
    assert "GOOGL" in sim.get_tickers()
    assert sim.get_price("GOOGL") == SEED_PRICES["GOOGL"]


def test_add_ticker_is_noop_if_already_present():
    sim = GBMSimulator(tickers=["AAPL"])
    price_before = sim.get_price("AAPL")
    sim.add_ticker("AAPL")
    assert sim.get_tickers().count("AAPL") == 1
    assert sim.get_price("AAPL") == price_before


def test_add_ticker_rebuilds_cholesky_to_match_new_size():
    sim = GBMSimulator(tickers=["AAPL"])
    sim.add_ticker("GOOGL")
    sim.add_ticker("MSFT")
    assert sim._cholesky is not None
    assert sim._cholesky.shape == (3, 3)


def test_remove_ticker_removes_from_all_internal_state():
    sim = GBMSimulator(tickers=["AAPL", "GOOGL"])
    sim.remove_ticker("AAPL")
    assert "AAPL" not in sim.get_tickers()
    assert sim.get_price("AAPL") is None
    assert "AAPL" not in sim._params


def test_remove_ticker_is_noop_if_not_present():
    sim = GBMSimulator(tickers=["AAPL"])
    sim.remove_ticker("NOPE")
    assert sim.get_tickers() == ["AAPL"]


def test_remove_ticker_rebuilds_cholesky_to_match_new_size():
    sim = GBMSimulator(tickers=["AAPL", "GOOGL", "MSFT"])
    sim.remove_ticker("GOOGL")
    assert sim._cholesky.shape == (2, 2)


def test_cholesky_is_none_for_single_ticker():
    sim = GBMSimulator(tickers=["AAPL"])
    assert sim._cholesky is None


def test_cholesky_is_none_for_zero_tickers():
    sim = GBMSimulator(tickers=[])
    assert sim._cholesky is None


@pytest.mark.parametrize(
    ("t1", "t2", "expected"),
    [
        ("AAPL", "GOOGL", INTRA_TECH_CORR),
        ("MSFT", "NVDA", INTRA_TECH_CORR),
        ("JPM", "V", INTRA_FINANCE_CORR),
        ("TSLA", "AAPL", TSLA_CORR),
        ("AAPL", "TSLA", TSLA_CORR),
        ("TSLA", "JPM", TSLA_CORR),
        ("AAPL", "JPM", CROSS_GROUP_CORR),
        ("ZZZZ", "AAPL", CROSS_GROUP_CORR),
        ("ZZZZ", "YYYY", CROSS_GROUP_CORR),
    ],
)
def test_pairwise_correlation(t1, t2, expected):
    assert GBMSimulator._pairwise_correlation(t1, t2) == expected


def test_default_params_used_for_unknown_ticker():
    sim = GBMSimulator(tickers=["ZZZZ"])
    assert sim._params["ZZZZ"] == DEFAULT_PARAMS
