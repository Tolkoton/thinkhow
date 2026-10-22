"""conversation.md: markdown a person reads, with HTML-comment markers the code parses (ADR-0004).

A text line that starts with the marker prefix or with a backslash gets one more backslash when written;
reading takes one off (I1). Nothing here touches storage.
"""

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

PREFIX = "<!-- thinkhow:"
FORMAT_LINE = "<!-- thinkhow:format 1 -->"
STAMP = "%Y-%m-%dT%H:%M:%SZ"
SESSION = re.compile(r"^<!-- thinkhow:session (\d+) -->$")
TURN = re.compile(r"^<!-- thinkhow:turn (\d+) (user|model) (\S+) -->$")
CLOSED = re.compile(r"^<!-- thinkhow:closed (\d+) (\S+) -->$")


@dataclass
class Turn:
    no: int
    role: Literal["user", "model"]
    at: datetime
    text: str


@dataclass
class SessionDoc:
    no: int
    turns: list[Turn] = field(default_factory=list)
    closed_at: datetime | None = None


@dataclass
class Conversation:
    title: str
    sessions: list[SessionDoc]

    def last_no(self) -> int:
        return max((t.no for s in self.sessions for t in s.turns), default=0)


def normalize(text: str) -> str:
    """\\r\\n and \\r become \\n; the edges of the whole text are trimmed (Q2)."""
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def normalize_title(title: str) -> str:
    return normalize(title).replace("\n", " ").strip()


def stamp(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime(STAMP)


def second(moment: datetime) -> datetime:
    """The moment as the file keeps it: UTC, cut to the second."""
    return moment.astimezone(UTC).replace(microsecond=0)


def render(conv: Conversation) -> str:
    lines = [FORMAT_LINE, f"# {_escape(conv.title)}", ""]
    for session in conv.sessions:
        lines += [f"<!-- thinkhow:session {session.no} -->", ""]
        for turn in session.turns:
            lines += [
                f"<!-- thinkhow:turn {turn.no} {turn.role} {stamp(turn.at)} -->",
                _escape(turn.text),
                "",
            ]
        if session.closed_at is not None:
            lines += [f"<!-- thinkhow:closed {session.no} {stamp(session.closed_at)} -->", ""]
    return "\n".join(lines)


def parse(text: str) -> Conversation:
    """Flow: the title line → markers open sessions and turns; every other line belongs to the open turn."""
    lines = text.split("\n")
    title = _unescape(lines[1][2:]) if len(lines) > 1 and lines[1].startswith("# ") else ""
    conv, body = Conversation(title=title, sessions=[]), []
    for line in lines[2:]:
        if not line.startswith(PREFIX):
            body.append(line)
            continue
        _close_body(conv, body)
        body = []
        _apply_marker(conv, line)
    _close_body(conv, body)
    return conv


def _apply_marker(conv: Conversation, line: str) -> None:
    if m := SESSION.match(line):
        conv.sessions.append(SessionDoc(no=int(m.group(1))))
    elif m := TURN.match(line):
        role: Literal["user", "model"] = "user" if m.group(2) == "user" else "model"
        conv.sessions[-1].turns.append(Turn(int(m.group(1)), role, _parse_stamp(m.group(3)), ""))
    elif m := CLOSED.match(line):
        conv.sessions[-1].closed_at = _parse_stamp(m.group(2))


def _close_body(conv: Conversation, body: list[str]) -> None:
    while body and body[-1] == "":
        body.pop()
    while body and body[0] == "":
        body.pop(0)
    if conv.sessions and conv.sessions[-1].turns and not conv.sessions[-1].turns[-1].text:
        conv.sessions[-1].turns[-1].text = "\n".join(_unescape(line) for line in body)


def _escape(line_block: str) -> str:
    return "\n".join("\\" + ln if ln.startswith((PREFIX, "\\")) else ln for ln in line_block.split("\n"))


def _unescape(line: str) -> str:
    return line[1:] if line.startswith("\\") else line


def _parse_stamp(value: str) -> datetime:
    return datetime.strptime(value, STAMP).replace(tzinfo=UTC)
