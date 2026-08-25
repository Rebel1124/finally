"""FastAPI app: wires the database, market data source, and API routers together."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.chat.router import router as chat_router
from app.db import init_db
from app.db import repository as db
from app.market.cache import PriceCache
from app.market.factory import create_market_data_source
from app.market.stream import create_stream_router
from app.portfolio import service as portfolio_service
from app.portfolio.router import router as portfolio_router
from app.watchlist import service as watchlist_service
from app.watchlist.router import router as watchlist_router

SNAPSHOT_INTERVAL_SECONDS = 30
FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "out"

# A single PriceCache instance backs the whole app for its lifetime; the market
# data source is (re)created and started fresh on each lifespan startup.
price_cache = PriceCache()


async def _snapshot_loop() -> None:
    while True:
        await asyncio.sleep(SNAPSHOT_INTERVAL_SECONDS)
        db.insert_snapshot(portfolio_service.get_portfolio()["total_value"])


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_db()

    market_source = create_market_data_source(price_cache)
    tickers = [row["ticker"] for row in db.list_watchlist()]
    await market_source.start(tickers)

    portfolio_service.init(price_cache)
    watchlist_service.init(price_cache, market_source)

    snapshot_task = asyncio.create_task(_snapshot_loop(), name="portfolio-snapshot-loop")

    yield

    snapshot_task.cancel()
    try:
        await snapshot_task
    except asyncio.CancelledError:
        pass
    await market_source.stop()


app = FastAPI(title="FinAlly", lifespan=lifespan)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


app.include_router(create_stream_router(price_cache))
app.include_router(portfolio_router)
app.include_router(watchlist_router)
app.include_router(chat_router)

if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="static")
