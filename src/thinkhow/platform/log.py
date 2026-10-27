"""Structured logs: one JSON line per event on stdout, with the request id (M3 A4).

Callers never pass conversation text here.
"""

import json
import sys
from contextvars import ContextVar
from typing import TextIO

request_id: ContextVar[str | None] = ContextVar("request_id", default=None)


def log_event(event: str, stream: TextIO | None = None, **fields: object) -> None:
    """`event` and the context's request id win over fields of the same name; severity defaults to INFO.
    No stream: the stdout of the moment (so a redirect of stdout catches the line)."""
    line = {"severity": "INFO", **fields, "event": event, "request_id": request_id.get()}
    stream = stream or sys.stdout
    stream.write(json.dumps(line, ensure_ascii=False, default=str) + "\n")
    stream.flush()
