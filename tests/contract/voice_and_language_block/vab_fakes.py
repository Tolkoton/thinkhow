"""Helpers for the voice-and-language block (integration) tests. Slice tester, mode `block`;
written from `.engine/architecture/feature/voice-and-language.md` and the public signatures.

- RecordingSpeech: a `Speech` of the tests' own; remembers (audio, mime, language); returns `text`,
  or raises the next planned exception first.
- RecordingLlm: an `Llm` that records every `system` it is given and forwards to a scripted double.
- FakeFacilitate: a `Facilitate` written by hand: records each `FacilitationContext`, answers once.
- make_app: the real `create_app(Deps(...))` with a local folder, IAP identity over fake tokens,
  the given speech and facilitate.
- sse_events: the SSE body of the reply route as a list of (event, data).
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from pydantic import BaseModel

from thinkhow.access import CurrentUser
from thinkhow.facilitation.types import (
    Facilitate,
    FacilitationContext,
    FacilitatorUpdate,
    MapUpdate,
    ReplyDelta,
)
from thinkhow.platform.config import load_settings
from thinkhow.platform.identity import IapIdentity
from thinkhow.platform.llm import Done, KnowledgeRev, Turn
from thinkhow.platform.llm import ReplyDelta as LlmDelta
from thinkhow.platform.speech import Speech
from thinkhow.platform.storage import LocalStorage
from thinkhow.web.server import Deps, create_app

REPO = Path(__file__).resolve().parents[3]
CARDS = REPO / "cards"
T0 = datetime(2026, 10, 23, 21, 0, 0, tzinfo=UTC)

ALICE = CurrentUser(id="alice-1", email="alice@example.com", is_owner=False)
BOB = CurrentUser(id="bob_2", email="bob@example.com", is_owner=False)

IAP = "x-goog-iap-jwt-assertion"
TOKENS: dict[str, dict[str, str]] = {
    "tok-alice": {"sub": "accounts.google.com:alice-1", "email": "alice@example.com"},
    "tok-bob": {"sub": "accounts.google.com:bob_2", "email": "bob@example.com"},
}
H_ALICE = {IAP: "tok-alice"}
H_BOB = {IAP: "tok-bob"}

AUDIO = b"\x1aE\xdf\xa3 fake webm opus bytes \x00\x01\x02"
WEBM = "audio/webm;codecs=opus"


def verify_fake(token: str, audience: str) -> Mapping[str, object]:
    if token not in TOKENS:
        raise RuntimeError("bad signature")
    return TOKENS[token]


@dataclass
class RecordingSpeech:
    text: str = "розпізнаний текст"
    fail_first: list[BaseException] = field(default_factory=list)
    calls: list[tuple[bytes, str, str]] = field(default_factory=list)

    def transcribe(self, audio: bytes, mime: str, language: str) -> str:
        self.calls.append((audio, mime, language))
        if self.fail_first:
            raise self.fail_first.pop(0)
        return self.text


@dataclass
class RecordingLlm:
    inner: Any
    systems: list[str] = field(default_factory=list)

    def stream_json(
        self, system: str, contents: Sequence[Turn], schema: type[BaseModel], rev: KnowledgeRev | None
    ) -> Iterator[LlmDelta | Done]:
        self.systems.append(system)
        yield from self.inner.stream_json(system, contents, schema, rev)

    def generate_json(
        self, system: str, contents: Sequence[Turn], schema: type[Any], rev: KnowledgeRev | None
    ) -> Any:
        self.systems.append(system)
        return self.inner.generate_json(system, contents, schema, rev)


@dataclass
class FakeFacilitate:
    contexts: list[FacilitationContext] = field(default_factory=list)

    def __call__(self, ctx: FacilitationContext) -> Iterator[ReplyDelta | FacilitatorUpdate]:
        self.contexts.append(ctx)
        yield ReplyDelta("Що далі?")
        yield FacilitatorUpdate(
            reply="Що далі?",
            current_phase_id="p1",
            phase_exit_met=False,
            map_updates=[
                MapUpdate(op="add", id=f"i{ctx.turn_no}", type="plan", text=ctx.text, turn=f"t{ctx.turn_no}")
            ],
        )


def _never_facilitate(ctx: FacilitationContext) -> Iterator[ReplyDelta | FacilitatorUpdate]:
    raise AssertionError("facilitate is not called in this test")


@dataclass
class App:
    client: TestClient
    storage: LocalStorage


def make_app(
    tmp_path: Path, speech: Speech, facilitate: Facilitate | None = None, storage: LocalStorage | None = None
) -> App:
    store = storage if storage is not None else LocalStorage(tmp_path / "data")
    settings = load_settings(
        {
            "THINKHOW_LOCAL": "true",
            "THINKHOW_LOCAL_DIR": str(tmp_path),
            "THINKHOW_OWNER_EMAIL": "owner@example.com",
        }
    )
    deps = Deps(
        storage=store,
        identity=IapIdentity("aud-test", verify_fake),
        settings=settings,
        facilitate=facilitate if facilitate is not None else _never_facilitate,
        now=lambda: T0,
        speech=speech,
    )
    client = TestClient(create_app(deps), raise_server_exceptions=False, follow_redirects=False)
    return App(client, store)


def profile(store: LocalStorage, user: CurrentUser) -> dict[str, Any] | None:
    raw = store.read("users", f"{user.id}/profile.json")
    return None if raw is None else json.loads(raw)


def sse_events(body: str) -> list[tuple[str, dict[str, Any]]]:
    events = []
    for block in body.strip().split("\n\n"):
        lines = block.split("\n")
        name = next(x for x in lines if x.startswith("event:")).split(":", 1)[1].strip()
        data = next(x for x in lines if x.startswith("data:")).split(":", 1)[1].strip()
        events.append((name, json.loads(data)))
    return events


def local_environ(folder: Path) -> dict[str, str]:
    return {
        "THINKHOW_LOCAL": "true",
        "THINKHOW_LOCAL_DIR": str(folder),
        "THINKHOW_OWNER_EMAIL": "owner@localhost",
    }
