"""Tests for app.chat.llm, with litellm.completion monkeypatched (no real network calls)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app import chat
from app.chat import llm
from app.db import repository as repo
from app.market.cache import PriceCache
from app.portfolio import service as portfolio_service
from app.watchlist import service as watchlist_service


class _FakeMarketSource:
    async def add_ticker(self, ticker):
        pass

    async def remove_ticker(self, ticker):
        pass


@pytest.fixture(autouse=True)
def wired(db):
    cache = PriceCache()
    cache.update("AAPL", 190.0)
    portfolio_service.init(cache)
    watchlist_service.init(cache, _FakeMarketSource())
    return cache


def _fake_completion_response(content: str):
    message = SimpleNamespace(content=content)
    choice = SimpleNamespace(message=message)
    return SimpleNamespace(choices=[choice])


def test_get_llm_response_parses_structured_output(monkeypatch):
    canned_json = (
        '{"message": "Buying 1 AAPL.", '
        '"trades": [{"ticker": "AAPL", "side": "buy", "quantity": 1}], '
        '"watchlist_changes": []}'
    )

    captured = {}

    def fake_completion(**kwargs):
        captured.update(kwargs)
        return _fake_completion_response(canned_json)

    monkeypatch.setattr(chat.llm, "completion", fake_completion)

    repo.insert_chat_message("user", "buy 1 AAPL")
    result = llm.get_llm_response()

    assert result.message == "Buying 1 AAPL."
    assert result.trades[0].ticker == "AAPL"
    assert captured["model"] == llm.MODEL
    assert captured["extra_body"] == llm.EXTRA_BODY
    assert captured["response_format"] is llm.LLMResponse
    assert captured["messages"][0]["role"] == "system"
    assert captured["messages"][-1] == {"role": "user", "content": "buy 1 AAPL"}


def test_build_messages_includes_portfolio_context(monkeypatch):
    repo.insert_chat_message("user", "how's my portfolio?")

    messages = llm.build_messages()

    assert "Cash balance" in messages[0]["content"]
    assert messages[-1] == {"role": "user", "content": "how's my portfolio?"}
