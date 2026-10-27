"""The one retry rule of Vertex calls (M3 A4), shared by platform.llm, platform.speech and platform.tts.

Kept apart so that platform.speech never imports platform.llm (workspace may not reach it, even indirectly).
"""

import random

import httpx
import httpx2
from google.genai import errors


def retryable(exc: Exception) -> bool:
    """A timeout, 429 or a 5xx is worth another attempt; anything else is not."""
    if isinstance(exc, (httpx.TimeoutException, httpx2.TimeoutException)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        return status == 429 or status >= 500
    return isinstance(exc, errors.APIError) and (exc.code == 429 or exc.code >= 500)


def backoff_s(attempt: int) -> float:
    return float(min(2**attempt, 30) * random.uniform(0.5, 1.0))
