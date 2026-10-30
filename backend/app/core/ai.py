import asyncio
import logging
import os
from typing import Any, Optional

from google import genai

from app.core.config import settings

logger = logging.getLogger(__name__)


def _configured_api_keys() -> list[str]:
    candidates = [
        settings.GEMINI_API_KEY,
        os.getenv("GEMINI_API_KEYY", ""),
        settings.GEMINI_API_KEY_BACKUP,
        os.getenv("GEMINI_API_KEY_2", ""),
    ]
    return list(dict.fromkeys(key.strip() for key in candidates if key and key.strip()))


async def generate_content_with_fallback(
    *,
    model: str,
    contents: Any,
    config: Optional[Any] = None,
) -> Any:
    api_keys = _configured_api_keys()
    if not api_keys:
        raise RuntimeError(
            "No Gemini API key is configured. Set GEMINI_API_KEY or "
            "GEMINI_API_KEY_BACKUP in the backend environment."
        )

    last_error: Optional[Exception] = None
    for index, api_key in enumerate(api_keys):
        try:
            client = genai.Client(api_key=api_key)
            return await asyncio.to_thread(
                client.models.generate_content,
                model=model,
                contents=contents,
                config=config,
            )
        except Exception as error:
            last_error = error
            if index < len(api_keys) - 1:
                logger.warning(
                    "Gemini request failed with key %d; trying configured backup key",
                    index + 1,
                )

    raise RuntimeError("All configured Gemini API keys failed") from last_error
