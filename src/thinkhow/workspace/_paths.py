"""The small shared pieces of the users bucket's paths: the server id rule and the JSON content type.

A leaf of workspace, so that profile and topics can both use them without importing each other.
"""

import re

UID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
JSON = "application/json"


def _uid(uid: str) -> str:
    if not UID.match(uid):
        raise ValueError(f"not a server id: {uid!r}")
    return uid
