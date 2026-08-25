"""Calls the LLM (via LiteLLM -> OpenRouter -> Cerebras) for a structured chat response."""

from __future__ import annotations

from litellm import completion

from app.db import repository as db

from .context import SYSTEM_PROMPT, build_portfolio_context
from .schemas import LLMResponse

MODEL = "openrouter/openai/gpt-oss-120b"
EXTRA_BODY = {"provider": {"order": ["cerebras"]}}


def build_messages() -> list[dict]:
    """System prompt + portfolio context, followed by recent chat history.

    The caller stores the new user message before calling this, so it's
    already the newest entry returned by list_recent_chat_messages.
    """
    system_content = f"{SYSTEM_PROMPT}\n\n{build_portfolio_context()}"
    messages = [{"role": "system", "content": system_content}]
    messages += [
        {"role": m["role"], "content": m["content"]} for m in db.list_recent_chat_messages(limit=20)
    ]
    return messages


def get_llm_response() -> LLMResponse:
    messages = build_messages()
    response = completion(
        model=MODEL,
        messages=messages,
        response_format=LLMResponse,
        reasoning_effort="medium",
        extra_body=EXTRA_BODY,
    )
    return LLMResponse.model_validate_json(response.choices[0].message.content)
