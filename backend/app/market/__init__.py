"""Market data subsystem: unified interface, GBM simulator, and Massive API client.

Public exports:

    from app.market import (
        PriceUpdate,
        PriceCache,
        MarketDataSource,
        SimulatorDataSource,
        GBMSimulator,
        MassiveDataSource,
        create_market_data_source,
        create_stream_router,
    )
"""

from __future__ import annotations

from .cache import PriceCache
from .factory import create_market_data_source
from .interface import MarketDataSource
from .massive_client import MassiveDataSource
from .models import PriceUpdate
from .simulator import GBMSimulator, SimulatorDataSource
from .stream import create_stream_router

__all__ = [
    "PriceUpdate",
    "PriceCache",
    "MarketDataSource",
    "SimulatorDataSource",
    "GBMSimulator",
    "MassiveDataSource",
    "create_market_data_source",
    "create_stream_router",
]
