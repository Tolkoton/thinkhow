"""Pull the text of the first JSON field `reply` out of a JSON object that arrives in arbitrary pieces.

Used by platform.llm only. Knows nothing about Gemini: it is fed text and returns decoded text.
"""

import json
import re

HEX4 = re.compile(r"[0-9a-fA-F]{4}")
WHITESPACE = " \t\r\n"


class ReplyExtractor:
    """feed(piece) -> the newly decoded part of `reply`; "" when there is nothing new.

    Gives text only when `reply` is the first key of the top-level object; otherwise it stays silent
    (the caller still has the whole JSON at the end). States: object, key, colon, value, string, over.
    """

    def __init__(self) -> None:
        self.buffer = ""
        self.pos = 0
        self.state = "object"
        self.value_start = 0

    def feed(self, piece: str) -> str:
        self.buffer += piece
        while self.state not in ("string", "over"):
            if not self._advance_header():
                return ""
        return self._take_string() if self.state == "string" else ""

    def _advance_header(self) -> bool:
        """One step through `{ "reply" :  "`; False when it needs more text."""
        self._skip_whitespace()
        if self.pos >= len(self.buffer):
            return False
        if self.state == "object":
            return self._expect("{", "key")
        if self.state == "key":
            return self._read_key()
        if self.state == "colon":
            return self._expect(":", "value")
        self._expect('"', "string")
        self.value_start = self.pos
        return True

    def _skip_whitespace(self) -> None:
        while self.pos < len(self.buffer) and self.buffer[self.pos] in WHITESPACE:
            self.pos += 1

    def _expect(self, char: str, next_state: str) -> bool:
        if self.buffer[self.pos] == char:
            self.pos += 1
            self.state = next_state
        else:
            self.state = "over"
        return True

    def _read_key(self) -> bool:
        if self.buffer[self.pos] != '"':
            self.state = "over"
            return True
        end = self.buffer.find('"', self.pos + 1)
        if end < 0:
            return False
        self.state = "colon" if self.buffer[self.pos + 1 : end] == "reply" else "over"
        self.pos = end + 1
        return True

    def _take_string(self) -> str:
        """Decode the string content from value_start up to the last point where it is safe to cut."""
        safe, closed = _safe_end(self.buffer, self.value_start)
        text = json.loads('"' + self.buffer[self.value_start : safe] + '"') if safe > self.value_start else ""
        self.value_start = safe
        if closed:
            self.state = "over"
        return text


def _safe_end(buffer: str, start: int) -> tuple[int, bool]:
    """(index up to which the string content can be decoded alone, whether the closing quote was reached)."""
    i = start
    while i < len(buffer):
        char = buffer[i]
        if char == '"':
            return i, True
        if char != "\\":
            i += 1
            continue
        length = _escape_length(buffer, i)
        if length == 0:
            return i, False
        i += length
    return i, False


def _escape_length(buffer: str, i: int) -> int:
    """Length of the complete escape at i (a high surrogate keeps its low partner), 0 if incomplete."""
    if i + 1 >= len(buffer):
        return 0
    if buffer[i + 1] != "u":
        return 2
    code = buffer[i + 2 : i + 6]
    if len(code) < 4:
        return 0
    if not HEX4.fullmatch(code) or not 0xD800 <= int(code, 16) <= 0xDBFF:
        return 6
    tail = buffer[i + 6 : i + 12]
    if len(tail) < 6 and "\\u".startswith(tail[:2]):
        return 0
    return 12 if tail.startswith("\\u") and len(tail) == 6 else 6
