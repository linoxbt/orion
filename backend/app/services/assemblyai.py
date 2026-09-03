"""Shared AssemblyAI plumbing: endpoints, auth, and the LLM Gateway client.

Auth is not uniform across AssemblyAI's products and getting it wrong is the
most common integration failure:

  - Voice Agent API (wss://agents.assemblyai.com) wants "Authorization: Bearer <key>"
  - everything else - streaming, pre-recorded REST, LLM Gateway - wants the
    raw key with no prefix

Both header builders live here so no caller has to remember which is which.
"""

import json
import logging
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

REST_BASE = "https://api.assemblyai.com"
STREAMING_WS = "wss://streaming.assemblyai.com/v3/ws"
AGENTS_WS = "wss://agents.assemblyai.com/v1/ws"
LLM_GATEWAY_URL = "https://llm-gateway.assemblyai.com/v1/chat/completions"


class AssemblyAINotConfigured(RuntimeError):
    pass


def require_api_key() -> str:
    if not settings.assemblyai_api_key:
        raise AssemblyAINotConfigured("ASSEMBLYAI_API_KEY is not set")
    return settings.assemblyai_api_key


def rest_headers() -> dict[str, str]:
    """Streaming, pre-recorded REST and LLM Gateway: raw key, NO Bearer prefix."""
    return {"authorization": require_api_key()}


def agent_headers() -> dict[str, str]:
    """Voice Agent API only: this one product does take a Bearer prefix."""
    return {"Authorization": f"Bearer {require_api_key()}"}


async def llm_gateway_chat(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    max_tokens: int = 1000,
    timeout: float = 30.0,
) -> str:
    """One LLM Gateway chat completion, returning the assistant's text.

    Model ids are exact and versioned - see settings.llm_gateway_model. A bare
    family name is rejected.
    """
    payload: dict[str, Any] = {
        "model": model or settings.llm_gateway_model,
        "messages": messages,
        "max_tokens": max_tokens,
    }
    async with httpx.AsyncClient(timeout=timeout) as client:
        res = await client.post(
            LLM_GATEWAY_URL,
            headers={**rest_headers(), "content-type": "application/json"},
            json=payload,
        )
        res.raise_for_status()
        body = res.json()
    return body["choices"][0]["message"]["content"]


AGENTS_TOKEN_URL = "https://agents.assemblyai.com/v1/token"


async def mint_agent_token(expires_in_seconds: int = 300) -> str:
    """A short-lived, single-use token so a browser can open an agent session.

    The API key never reaches the browser: the browser gets a token that is
    good for one session and expires in minutes. Each reconnect needs a fresh
    one - these are not reusable.
    """
    async with httpx.AsyncClient(timeout=20.0) as client:
        res = await client.get(
            AGENTS_TOKEN_URL,
            headers=agent_headers(),
            params={"expires_in_seconds": expires_in_seconds},
        )
        res.raise_for_status()
    return res.json()["token"]


async def llm_gateway_completion(
    messages: list[dict[str, Any]],
    *,
    tools: list[dict[str, Any]] | None = None,
    model: str | None = None,
    max_tokens: int = 1000,
    timeout: float = 30.0,
) -> dict[str, Any]:
    """One LLM Gateway chat completion, returning the whole assistant message.

    Use this instead of llm_gateway_chat when the model may answer with
    tool_calls rather than text. LLM Gateway is OpenAI-compatible, so tools go
    in the NESTED form - {"type": "function", "function": {...}} - which is the
    opposite of the Voice Agent API's flat tool schema. The two are not
    interchangeable; app/services/call_tools.py holds the flat definitions and
    app/services/stt_bridge.py wraps them for this endpoint.
    """
    payload: dict[str, Any] = {
        "model": model or settings.llm_gateway_model,
        "messages": messages,
        "max_tokens": max_tokens,
    }
    if tools:
        payload["tools"] = tools

    async with httpx.AsyncClient(timeout=timeout) as client:
        res = await client.post(
            LLM_GATEWAY_URL,
            headers={**rest_headers(), "content-type": "application/json"},
            json=payload,
        )
        res.raise_for_status()
        body = res.json()
    return body["choices"][0]["message"]


async def llm_gateway_json(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    max_tokens: int = 1000,
) -> dict[str, Any] | None:
    """llm_gateway_chat, but parsing the reply as a JSON object.

    Models wrap JSON in markdown fences often enough that stripping them is
    worth doing here rather than in every caller. Returns None if the reply
    still isn't parseable - callers treat that as "extraction failed" and fall
    back to the human review queue rather than writing a guess into a
    negotiation's verified outcome.
    """
    raw = (await llm_gateway_chat(messages, model=model, max_tokens=max_tokens)).strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("LLM Gateway reply was not valid JSON: %.200s", raw)
        return None
    return parsed if isinstance(parsed, dict) else None
