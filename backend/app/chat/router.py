"""POST /api/chat: LLM-driven chat with auto-executed trades and watchlist changes."""

from __future__ import annotations

import json

from fastapi import APIRouter
from pydantic import BaseModel

from app import config
from app.db import repository as db
from app.portfolio import service as portfolio_service
from app.portfolio.service import TradeError
from app.watchlist import service as watchlist_service

from .llm import get_llm_response
from .mock import get_mock_response
from .schemas import LLMResponse

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str


async def _execute_trades(llm_response: LLMResponse) -> list[dict]:
    results = []
    for trade in llm_response.trades:
        item = {"ticker": trade.ticker, "side": trade.side, "quantity": trade.quantity}
        try:
            outcome = portfolio_service.execute_trade(trade.ticker, trade.side, trade.quantity)
            item["price"] = outcome["trade"]["price"]
            item["status"] = "executed"
        except TradeError as e:
            item["status"] = f"failed: {e}"
        results.append(item)
    return results


async def _execute_watchlist_changes(llm_response: LLMResponse) -> list[dict]:
    results = []
    for change in llm_response.watchlist_changes:
        item = {"ticker": change.ticker, "action": change.action}
        try:
            if change.action == "add":
                await watchlist_service.add_to_watchlist(change.ticker)
            else:
                await watchlist_service.remove_from_watchlist(change.ticker)
            item["status"] = "executed"
        except Exception as e:
            item["status"] = f"failed: {e}"
        results.append(item)
    return results


@router.post("")
async def post_chat(body: ChatRequest) -> dict:
    db.insert_chat_message("user", body.message)

    llm_response = get_mock_response(body.message) if config.LLM_MOCK else get_llm_response()

    trades = await _execute_trades(llm_response)
    watchlist_changes = await _execute_watchlist_changes(llm_response)

    actions_json = json.dumps({"trades": trades, "watchlist_changes": watchlist_changes})
    db.insert_chat_message("assistant", llm_response.message, actions_json=actions_json)

    return {"message": llm_response.message, "trades": trades, "watchlist_changes": watchlist_changes}
