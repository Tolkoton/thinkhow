"""Google's grounding redirect links → the address of the page, by one HEAD without following (S1b, A7).

Strings in, strings out: knows nothing of the model's answer. A failure of any kind keeps the Google link.
"""

from collections.abc import Callable

import httpx

Head = Callable[[str, float], tuple[int, str | None]]
REDIRECTS = (301, 302, 303, 307, 308)
ABSOLUTE = ("http://", "https://")
GOOGLE_REDIRECT = "https://vertexaisearch.cloud.google.com/grounding-api-redirect/"


def resolve_link(url: str, head: Head, timeout_s: float = 3.0) -> str:
    """The page a Google redirect link points to; any other address, or any failure, gives `url` back."""
    if not url.startswith(GOOGLE_REDIRECT):
        return url
    try:
        status, location = head(url, timeout_s)
    except Exception:
        return url
    if status in REDIRECTS and isinstance(location, str) and location.startswith(ABSOLUTE):
        return location
    return url


def httpx_head(url: str, timeout_s: float) -> tuple[int, str | None]:
    """One HEAD without following redirects: the status and the Location header."""
    response = httpx.head(url, follow_redirects=False, timeout=timeout_s)
    return response.status_code, response.headers.get("location")
