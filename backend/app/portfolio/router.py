"""REST routes for portfolio and trade execution."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.db import repository as db

from . import service
from .service import TradeError

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


class TradeRequest(BaseModel):
    ticker: str
    quantity: float
    side: Literal["buy", "sell"]


@router.get("")
def get_portfolio() -> dict:
    return service.get_portfolio()


@router.post("/trade")
def post_trade(body: TradeRequest) -> dict:
    try:
        return service.execute_trade(body.ticker, body.side, body.quantity)
    except TradeError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/history")
def get_history() -> list[dict]:
    return [{"total_value": s["total_value"], "recorded_at": s["recorded_at"]} for s in db.list_snapshots()]
