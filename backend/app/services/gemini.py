from functools import lru_cache

from google import genai

from app.config import settings


class GeminiNotConfigured(RuntimeError):
    pass


@lru_cache
def get_client() -> genai.Client:
    if not settings.gemini_api_key:
        raise GeminiNotConfigured("GEMINI_API_KEY is not set")
    return genai.Client(api_key=settings.gemini_api_key)
