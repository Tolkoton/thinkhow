"""Helper for the voice-synthesis catch-up tests of the spike `gemini_limit.py` (slice tester).

Its public surface, as the contract and the record show it: run from the repository root, it probes
Gemini-TTS on the `eu` endpoint with texts of several sizes and gives one block per size, starting with a
line `<n> bytes: <status> <the start of Google's answer>`; `gemini_limit.out` is that output.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SPIKE = REPO / ".engine" / "artifacts" / "spikes" / "voice-conversation-2026-10-27"
SCRIPT = SPIKE / "gemini_limit.py"
RECORD = SPIKE / "gemini_limit.out"

_HEAD = re.compile(r"^(\d+) bytes: (\d{3})\b(.*)$")


def sizes_and_answers(text: str) -> dict[int, tuple[int, str]]:
    """{size in bytes: (HTTP status, the answer's text up to the next size line)}."""
    found: dict[int, tuple[int, str]] = {}
    current: int | None = None
    for line in text.splitlines():
        head = _HEAD.match(line.strip())
        if head:
            current = int(head.group(1))
            found[current] = (int(head.group(2)), head.group(3))
        elif current is not None:
            status, answer = found[current]
            found[current] = (status, answer + "\n" + line)
    return found
