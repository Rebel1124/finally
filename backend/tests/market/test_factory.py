"""Tests for app.market.factory.create_market_data_source."""

from __future__ import annotations

import pytest

from app.market.cache import PriceCache
from app.market.factory import create_market_data_source
from app.market.massive_client import MassiveDataSource
from app.market.simulator import SimulatorDataSource


@pytest.fixture
def cache() -> PriceCache:
    return PriceCache()


def test_no_env_var_returns_simulator(monkeypatch, cache):
    monkeypatch.delenv("MASSIVE_API_KEY", raising=False)
    source = create_market_data_source(cache)
    assert isinstance(source, SimulatorDataSource)


def test_empty_env_var_returns_simulator(monkeypatch, cache):
    monkeypatch.setenv("MASSIVE_API_KEY", "")
    source = create_market_data_source(cache)
    assert isinstance(source, SimulatorDataSource)


def test_whitespace_only_env_var_returns_simulator(monkeypatch, cache):
    monkeypatch.setenv("MASSIVE_API_KEY", "   ")
    source = create_market_data_source(cache)
    assert isinstance(source, SimulatorDataSource)


def test_present_env_var_returns_massive_source(monkeypatch, cache):
    monkeypatch.setenv("MASSIVE_API_KEY", "test-key-123")
    source = create_market_data_source(cache)
    assert isinstance(source, MassiveDataSource)


def test_env_var_is_stripped_before_use(monkeypatch, cache):
    monkeypatch.setenv("MASSIVE_API_KEY", "  test-key-123  ")
    source = create_market_data_source(cache)
    assert isinstance(source, MassiveDataSource)
    assert source._api_key == "test-key-123"


def test_returned_source_is_unstarted(monkeypatch, cache):
    monkeypatch.delenv("MASSIVE_API_KEY", raising=False)
    source = create_market_data_source(cache)
    assert source.get_tickers() == []


def test_factory_returns_new_instance_each_call(monkeypatch, cache):
    monkeypatch.delenv("MASSIVE_API_KEY", raising=False)
    source_a = create_market_data_source(cache)
    source_b = create_market_data_source(cache)
    assert source_a is not source_b
