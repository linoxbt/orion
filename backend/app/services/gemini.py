"""The Gemini client, and the one structured job that is worth its own model.

Bill extraction has always run here, because it is multimodal. The post-call
outcome extraction now prefers it too - see `structured_json` for why.
"""

import json
import logging
from functools import lru_cache

from google import genai

from app.config import settings

logger = logging.getLogger(__name__)


class GeminiNotConfigured(RuntimeError):
    pass


@lru_cache
def get_client() -> genai.Client:
    if not settings.gemini_api_key:
        raise GeminiNotConfigured("GEMINI_API_KEY is not set")
    return genai.Client(api_key=settings.gemini_api_key)


def is_configured() -> bool:
    return bool(settings.gemini_api_key)


async def structured_json(instruction: str, content: str) -> dict | None:
    """One JSON answer from the first model in the extraction chain.

    Returns None on any failure so the caller can fall back rather than lose
    the outcome entirely.
    """
    try:
        client = get_client()
    except GeminiNotConfigured:
        return None

    model = settings.gemini_model_chain[0]
    try:
        response = await client.aio.models.generate_content(
            model=model,
            contents=[f"{instruction}\n\n---\n\n{content}"],
            config={"response_mime_type": "application/json"},
        )
    except Exception as exc:  # noqa: BLE001 - the caller has a fallback
        logger.warning("Gemini extraction failed on %s: %s", model, exc)
        return None

    raw = (response.text or "").strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Gemini extraction was not valid JSON: %.200s", raw)
        return None
    return parsed if isinstance(parsed, dict) else None
