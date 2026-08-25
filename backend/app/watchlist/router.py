"""REST routes for watchlist management."""

from __future__ import annotations

from fastapi import APIRouter, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.db import repository as db

from . import service

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


class WatchlistAddRequest(BaseModel):
    ticker: str


@router.get("")
def get_watchlist() -> list[dict]:
    return service.get_watchlist()


@router.post("")
async def post_watchlist(body: WatchlistAddRequest) -> JSONResponse:
    ticker = body.ticker.strip().upper()
    already_present = any(row["ticker"] == ticker for row in db.list_watchlist())
    entry = await service.add_to_watchlist(ticker)
    status_code = 200 if already_present else 201
    return JSONResponse(content=entry, status_code=status_code)


@router.delete("/{ticker}", status_code=204)
async def delete_watchlist(ticker: str) -> Response:
    await service.remove_from_watchlist(ticker)
    return Response(status_code=204)
