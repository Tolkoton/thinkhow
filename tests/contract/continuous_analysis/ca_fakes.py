"""Helpers for the continuous-analysis contract tests (slice tester). Built from the contract, not the code.

- Topics are made through workspace itself (`create_topic`, `reply`, `retry`) with an injected `now`;
  a legacy topic (a `closed` marker, written by an earlier version) is a hand-written `conversation.md`
  in the format of ADR-0004 laid over a topic made by `create_topic`.
- FakeLlm: an `Llm` double for `generate_json`; records every call; answers with the last (or the first)
  anchor of the schema's enum, or raises the exception planned for the run.
- SpyStorage: a `LocalStorage` that records every write (`write` and `create_if_absent`).
- observations(): the file names under `system/learning/observations/<uid>/<topic>/` and their JSON.
- make_client: the web app over the same storage (a person with a chosen language).
"""

from __future__ import annotations

import io
import json
import re
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel, ValidationError

import thinkhow.platform.log as log
from thinkhow.access import CurrentUser
from thinkhow.facilitation.types import FacilitationContext, FacilitatorUpdate, ReplyDelta
from thinkhow.platform.config import load_settings
from thinkhow.platform.identity import IapIdentity
from thinkhow.platform.llm import KnowledgeRev, Turn
from thinkhow.platform.speech import ScriptedSpeech
from thinkhow.platform.storage import Bucket, LocalStorage
from thinkhow.web.server import Deps, create_app
from thinkhow.workspace import TopicRef, create_topic, reply, retry, set_language

NOW = datetime(2026, 10, 23, 3, 0, 0, tzinfo=UTC)
H = timedelta(hours=1)
M = timedelta(minutes=1)
S1 = timedelta(seconds=1)
DAY = timedelta(hours=25)  # more than the 24 h of silence: a new session

ALICE = CurrentUser(id="alice-1", email="alice@example.com", is_owner=False)
BOB = CurrentUser(id="bob_2", email="bob@example.com", is_owner=False)

CTX = "[Контекст — уже проаналізовано, не якір:]"
NEW = "[Нові репліки:]"

IAP = "x-goog-iap-jwt-assertion"
TOKENS: dict[str, dict[str, str]] = {
    "tok-alice": {"sub": "accounts.google.com:alice-1", "email": "alice@example.com"},
}
H_ALICE = {IAP: "tok-alice"}


# --- topics ----------------------------------------------------------------------------------------


def update(text: str) -> FacilitatorUpdate:
    return FacilitatorUpdate(reply=text, current_phase_id="p1", phase_exit_met=False, map_updates=[])


class Down(Exception):
    """The facilitator's model failed: the person's turn stays without an answer."""


@dataclass
class OneAnswer:
    """A `Facilitate` that answers once with `answer` (or raises `Down` when `answer` is None)."""

    answer: str | None

    def __call__(self, context: FacilitationContext) -> Iterator[ReplyDelta | FacilitatorUpdate]:
        return self._run()

    def _run(self) -> Iterator[ReplyDelta | FacilitatorUpdate]:
        if self.answer is None:
            raise Down("down")
        yield ReplyDelta(text=self.answer)
        yield update(self.answer)


def new_topic(storage: LocalStorage, user: CurrentUser, at: datetime, title: str = "Тема") -> TopicRef:
    return TopicRef(user.id, create_topic(storage, user, title, at))


def say(
    storage: LocalStorage, user: CurrentUser, ref: TopicRef, text: str, answer: str, at: datetime
) -> None:
    """The person's turn and the facilitator's answer (two turns), at `at`."""
    list(reply(storage, OneAnswer(answer), user, ref, text, at))


def say_unanswered(storage: LocalStorage, user: CurrentUser, ref: TopicRef, text: str, at: datetime) -> None:
    """The person's turn is saved, the answer fails: one turn."""
    list(reply(storage, OneAnswer(None), user, ref, text, at))


def answer_now(storage: LocalStorage, user: CurrentUser, ref: TopicRef, answer: str, at: datetime) -> None:
    """`retry`: the answer to the person's unanswered turn (one turn)."""
    list(retry(storage, OneAnswer(answer), user, ref, at))


def stamp(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class LT:
    """One turn of a hand-written (legacy) conversation.md."""

    no: int
    role: str
    text: str
    at: datetime


@dataclass
class LS:
    """One session of a hand-written conversation.md; `closed`: the time of its legacy `closed` marker."""

    no: int
    turns: list[LT]
    closed: datetime | None = None


def conversation_md(title: str, sessions: Sequence[LS]) -> str:
    lines = ["<!-- thinkhow:format 1 -->", f"# {title}"]
    for s in sessions:
        lines.append(f"<!-- thinkhow:session {s.no} -->")
        for t in s.turns:
            lines.append(f"<!-- thinkhow:turn {t.no} {t.role} {stamp(t.at)} -->")
            lines.append(t.text)
        if s.closed is not None:
            lines.append(f"<!-- thinkhow:closed {s.no} {stamp(s.closed)} -->")
    return "\n".join(lines) + "\n"


def legacy_topic(
    storage: LocalStorage, user: CurrentUser, sessions: Sequence[LS], title: str = "Тема"
) -> TopicRef:
    """A topic made by `create_topic`, its conversation.md replaced by one an earlier version wrote."""
    first = min((t.at for s in sessions for t in s.turns), default=NOW - 30 * DAY)
    ref = new_topic(storage, user, first - H, title)
    storage.write("users", conv_path(ref), conversation_md(title, sessions).encode("utf-8"), MARKDOWN)
    return ref


MARKDOWN = "text/markdown; charset=utf-8"


def conv_path(ref: TopicRef) -> str:
    return f"{ref.uid}/{ref.topic_id}/conversation.md"


def pair(no: int, token: str, at: datetime) -> list[LT]:
    """Two legacy turns: the person's `no` and the facilitator's `no + 1`, both carrying `token`."""
    return [
        LT(no, "user", f"{token} людина {no}", at),
        LT(no + 1, "model", f"{token} фасилітатор {no + 1}", at + S1),
    ]


# --- observations ----------------------------------------------------------------------------------


def obs_dir(ref: TopicRef) -> str:
    return f"learning/observations/{ref.uid}/{ref.topic_id}/"


def obs_names(storage: LocalStorage, ref: TopicRef) -> set[str]:
    return {p.rsplit("/", 1)[-1] for p in storage.list("system", obs_dir(ref))}


def obs(storage: LocalStorage, ref: TopicRef, name: str) -> dict[str, Any]:
    raw = storage.read("system", obs_dir(ref) + name)
    assert raw is not None, f"no observation {name}"
    data = json.loads(raw)
    assert isinstance(data, dict)
    return data


def put_obs(storage: LocalStorage, ref: TopicRef, name: str, data: bytes | None = None) -> bytes:
    body = data if data is not None else b'{"legacy": true}'
    storage.write("system", obs_dir(ref) + name, body, "application/json")
    return body


def ranges(storage: LocalStorage, ref: TopicRef) -> list[tuple[int, int]]:
    """(first_turn, last_turn) of every `t<a>-t<b>.json` of the topic, from the JSON, sorted."""
    got = []
    for name in obs_names(storage, ref):
        if not re.fullmatch(r"t\d+-t\d+\.json", name):
            continue
        o = obs(storage, ref, name)
        got.append((int(o["first_turn"]), int(o["last_turn"])))
    return sorted(got)


@dataclass
class WriteRec:
    op: str
    bucket: Bucket
    path: str


class SpyStorage(LocalStorage):
    def __init__(self, root: Path) -> None:
        super().__init__(root)
        self.writes: list[WriteRec] = []

    def write(self, bucket: Bucket, path: str, data: bytes, content_type: str) -> None:
        self.writes.append(WriteRec("write", bucket, path))
        super().write(bucket, path, data, content_type)

    def create_if_absent(self, bucket: Bucket, path: str, data: bytes, content_type: str) -> bool:
        self.writes.append(WriteRec("create_if_absent", bucket, path))
        return super().create_if_absent(bucket, path, data, content_type)

    def system_writes(self) -> list[WriteRec]:
        return [w for w in self.writes if w.bucket == "system"]


# --- the model -------------------------------------------------------------------------------------


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

    def lines(self) -> list[str]:
        """The non-empty lines of the text (blank lines between blocks are not part of the contract)."""
        return [line for line in self.text.split("\n") if line.strip()]

    def anchors(self) -> list[str]:
        return enum_of(self.schema)


@dataclass
class FakeLlm:
    """`fail`: token in the call's text → the exception (an instance, or a factory taking the schema);
    `fail_all`: every call raises it. `pick`: "last" or "first" anchor of the enum."""

    fail: Mapping[str, Any] = field(default_factory=dict)
    fail_all: Any = None
    pick: str = "last"
    calls: list[LlmCall] = field(default_factory=list)

    def stream_json(self, *args: Any, **kwargs: Any) -> Any:
        raise AssertionError("the analyzer must use generate_json, not stream_json")

    def generate_json(
        self, system: str, contents: Sequence[Turn], schema: Any, rev: KnowledgeRev | None
    ) -> Any:
        call = LlmCall(system, list(contents), schema, rev)
        self.calls.append(call)
        planned = [exc for token, exc in self.fail.items() if token in call.text]
        if self.fail_all is not None:
            planned.append(self.fail_all)
        for exc in planned:
            raise exc(schema) if callable(exc) and not isinstance(exc, BaseException) else exc
        anchors = enum_of(schema)
        anchor = anchors[-1] if self.pick == "last" else anchors[0]
        return schema.model_validate(
            {
                "finding": "Фасилітатор поставив одне питання.",
                "worked": False,
                "cause": "method",
                "anchor": anchor,
            }
        )

    def calls_with(self, token: str) -> list[LlmCall]:
        return [c for c in self.calls if token in c.text]


# --- logs ------------------------------------------------------------------------------------------


class LogCapture:
    def __init__(self, capsys: Any) -> None:
        self.buffer = io.StringIO()
        self.capsys = capsys
        self._out = ""

    def lines(self) -> list[dict[str, Any]]:
        got = self.capsys.readouterr()
        self._out += got.out + "\n" + got.err
        found: list[dict[str, Any]] = []
        for line in (self.buffer.getvalue() + "\n" + self._out).splitlines():
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


# --- the web app -----------------------------------------------------------------------------------


def _verify(token: str, audience: str) -> Mapping[str, object]:
    if token not in TOKENS:
        raise RuntimeError("bad signature")
    return TOKENS[token]


def make_client(
    tmp_path: Path, storage: LocalStorage, now: Callable[[], datetime] = lambda: NOW
) -> TestClient:
    set_language(storage, ALICE, "uk-UA")
    settings = load_settings(
        {
            "THINKHOW_LOCAL": "true",
            "THINKHOW_LOCAL_DIR": str(tmp_path),
            "THINKHOW_OWNER_EMAIL": "owner@example.com",
        }
    )
    deps = Deps(
        storage=storage,
        identity=IapIdentity("aud-test", _verify),
        settings=settings,
        facilitate=OneAnswer("Так?"),
        now=now,
        speech=ScriptedSpeech("(локальний режим) розпізнаний текст"),
    )
    return TestClient(create_app(deps), raise_server_exceptions=False, follow_redirects=False)
