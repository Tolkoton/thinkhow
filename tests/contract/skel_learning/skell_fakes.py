"""Helpers for the skel-learning contract tests (slice tester). Built from the contract, not the code.

- write_topic: a hand-written `conversation.md` in the format of S4 (ADR-0004) in the `users` bucket.
- SpyStorage: a `LocalStorage` that records every write (`write` and `create_if_absent`) in order.
- FakeLlm: an `Llm` double for `generate_json`; records every call; answers with the LAST anchor of the
  schema's enum (or a chosen one), or raises the exception planned for a session (found by a token that
  appears in that session's turns).
- LogCapture: every JSON line written by `log_event` (its default stream redirected) or on stdout.
"""

from __future__ import annotations

import io
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

import thinkhow.platform.log as log
from thinkhow.platform.llm import KnowledgeRev, Turn
from thinkhow.platform.storage import Bucket, LocalStorage

NOW = datetime(2026, 10, 22, 18, 0, 0, tzinfo=UTC)
H24 = timedelta(hours=24)
S1 = timedelta(seconds=1)
REPO = Path(__file__).resolve().parents[3]
CARDS = REPO / "cards"

ALICE = "alice-1"
BOB = "bob_2"


def stamp(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class T:
    """One turn of a hand-written session: number, role, text, time."""

    no: int
    role: str
    text: str
    at: datetime


@dataclass
class S:
    """One session: number, turns, time of its legacy `closed` marker (None: no marker — the usual case now;
    the marker is only written here by hand, as data an earlier version left)."""

    no: int
    turns: list[T]
    closed: datetime | None = None


def conversation_md(title: str, sessions: Sequence[S]) -> str:
    lines = ["<!-- thinkhow:format 1 -->", f"# {title}"]
    for s in sessions:
        lines.append(f"<!-- thinkhow:session {s.no} -->")
        for t in s.turns:
            lines.append(f"<!-- thinkhow:turn {t.no} {t.role} {stamp(t.at)} -->")
            lines.append(t.text)
        if s.closed is not None:
            lines.append(f"<!-- thinkhow:closed {s.no} {stamp(s.closed)} -->")
    return "\n".join(lines) + "\n"


def write_topic(
    storage: LocalStorage, uid: str, topic_id: str, sessions: Sequence[S], title: str = "Тема"
) -> None:
    storage.write(
        "users",
        f"{uid}/{topic_id}/conversation.md",
        conversation_md(title, sessions).encode("utf-8"),
        "text/markdown; charset=utf-8",
    )


def obs_path(uid: str, topic_id: str, session_no: int) -> str:
    """A legacy observation file of an earlier version (continuous-analysis: only read, never written)."""
    return f"learning/observations/{uid}/{topic_id}/s{session_no}.json"


def range_path(uid: str, topic_id: str, first: int, last: int) -> str:
    """continuous-analysis, Seam step 4: `learning/observations/<uid>/<topic>/t<first>-t<last>.json`."""
    return f"learning/observations/{uid}/{topic_id}/t{first}-t{last}.json"


def observation_bytes(uid: str, topic_id: str, first: int, last: int, analyzed_at: datetime) -> bytes:
    """A present observation of turns `first..last` (anchored on `first`), as a JSON file of the new shape."""
    from thinkhow.learning.analyze import Observation

    return (
        Observation(
            uid=uid,
            topic_id=topic_id,
            first_turn=first,
            last_turn=last,
            turn=first,
            link=f"/topics/{uid}/{topic_id}#t{first}",
            worked=True,
            finding="Вже проаналізовано раніше.",
            cause="circumstances",
            analyzed_at=analyzed_at,
        )
        .model_dump_json()
        .encode("utf-8")
    )


@dataclass
class WriteRec:
    op: str
    bucket: Bucket
    path: str
    data: bytes
    content_type: str


class SpyStorage(LocalStorage):
    def __init__(self, root: Path) -> None:
        super().__init__(root)
        self.writes: list[WriteRec] = []

    def write(self, bucket: Bucket, path: str, data: bytes, content_type: str) -> None:
        self.writes.append(WriteRec("write", bucket, path, data, content_type))
        super().write(bucket, path, data, content_type)

    def create_if_absent(self, bucket: Bucket, path: str, data: bytes, content_type: str) -> bool:
        self.writes.append(WriteRec("create_if_absent", bucket, path, data, content_type))
        return super().create_if_absent(bucket, path, data, content_type)


def tree(root: Path) -> dict[str, bytes]:
    """Every file under `root`, by its path relative to `root`."""
    if not root.is_dir():
        return {}
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def enum_of(schema: type[BaseModel]) -> list[str]:
    prop = schema.model_json_schema()["properties"]["anchor"]
    return list(prop["enum"])


def validation_error(schema: type[BaseModel]) -> ValidationError:
    try:
        schema.model_validate({})
    except ValidationError as exc:
        return exc
    raise AssertionError("the schema accepted an empty answer")


@dataclass
class LlmCall:
    system: str
    contents: list[Turn]
    schema: type[BaseModel]
    rev: KnowledgeRev | None

    @property
    def text(self) -> str:
        return "\n".join(t.text for t in self.contents)


@dataclass
class FakeLlm:
    """`fail`: token in the session's text → the exception raised for that session (an instance or a factory
    taking the schema). `answer`: builds the answer dict from the schema's anchors (default: the last one)."""

    fail: Mapping[str, Any] = field(default_factory=dict)
    answer: Callable[[list[str]], dict[str, Any]] | None = None
    calls: list[LlmCall] = field(default_factory=list)

    def stream_json(self, *args: Any, **kwargs: Any) -> Any:
        raise AssertionError("the analyzer must use generate_json, not stream_json")

    def generate_json(
        self, system: str, contents: Sequence[Turn], schema: Any, rev: KnowledgeRev | None
    ) -> Any:
        call = LlmCall(system, list(contents), schema, rev)
        self.calls.append(call)
        for token, exc in self.fail.items():
            if token in call.text:
                raise exc(schema) if callable(exc) and not isinstance(exc, BaseException) else exc
        anchors = enum_of(schema)
        data = (
            self.answer(anchors)
            if self.answer is not None
            else {
                "finding": "Фасилітатор поставив одне питання.",
                "worked": False,
                "cause": "method",
                "anchor": anchors[-1],
            }
        )
        return schema.model_validate(data)

    def calls_with(self, token: str) -> list[LlmCall]:
        return [c for c in self.calls if token in c.text]


class LogCapture:
    def __init__(self, capsys: Any) -> None:
        self.buffer = io.StringIO()
        self.capsys = capsys
        self._out = ""
        self._err = ""

    def _read(self) -> None:
        got = self.capsys.readouterr()
        self._out += got.out
        self._err += got.err

    def err(self) -> str:
        self._read()
        return self._err

    def raw(self) -> str:
        self._read()
        return self.buffer.getvalue() + "\n" + self._out + "\n" + self._err

    def lines(self) -> list[dict[str, Any]]:
        found: list[dict[str, Any]] = []
        for line in self.raw().splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            if isinstance(obj, dict):
                found.append(obj)
        return found

    def events(self, name: str) -> list[dict[str, Any]]:
        return [line for line in self.lines() if line.get("event") == name]


def install_log_capture(monkeypatch: pytest.MonkeyPatch, capsys: Any) -> LogCapture:
    cap = LogCapture(capsys)
    monkeypatch.setattr(log.log_event, "__defaults__", (cap.buffer,))
    return cap


def local_environ(root: Path) -> dict[str, str]:
    return {
        "THINKHOW_LOCAL": "true",
        "THINKHOW_LOCAL_DIR": str(root),
        "THINKHOW_OWNER_EMAIL": "owner@localhost",
    }
