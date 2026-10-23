"""The person's language in users/<id>/profile.json (F13; M3 A3.3: workspace is its only writer).

Does NOT create the profile on login (that is ensure_profile) and knows nothing of speech or replies.
"""

import json

from thinkhow.access import CurrentUser
from thinkhow.platform.storage import Storage
from thinkhow.workspace.languages import LANGUAGES, Language
from thinkhow.workspace.topics import JSON, _uid

BY_CODE = {lang.code: lang for lang in LANGUAGES}


class NoLanguage(Exception):
    """The person has not chosen a language yet (or the profile holds none from the list)."""


def language(storage: Storage, user: CurrentUser) -> Language:
    """Flow: read profile.json → its `language` field → the listed Language; anything else is NoLanguage."""
    code = _language_field(storage.read("users", _path(user)))
    if code not in BY_CODE:
        raise NoLanguage(user.id)
    return BY_CODE[code]


def set_language(storage: Storage, user: CurrentUser, code: str) -> None:
    """Writes the whole profile from the request's person: nothing else lives in it (M2 S2)."""
    if code not in BY_CODE:
        raise ValueError(f"not a language of the list: {code!r}")
    data = json.dumps({"email": user.email, "language": code}, ensure_ascii=False).encode("utf-8")
    storage.write("users", _path(user), data, JSON)


def _language_field(data: bytes | None) -> str | None:
    """The `language` string, or None when absent, not UTF-8, not JSON, not an object or not a string."""
    if data is None:
        return None
    try:
        profile = json.loads(data.decode("utf-8"))
    except ValueError:
        return None
    code = profile.get("language") if isinstance(profile, dict) else None
    return code if isinstance(code, str) else None


def _path(user: CurrentUser) -> str:
    return f"{_uid(user.id)}/profile.json"
