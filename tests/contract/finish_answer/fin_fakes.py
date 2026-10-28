"""Helpers for the finish-answer contract tests (slice tester). Built from the contract
`.engine/slices/finish-answer.md` and the public signatures, not the code.

- Fac: a `Facilitate` double; each call takes the next planned script. A `str` is a `ReplyDelta`, a
  `FacilitatorUpdate` is yielded as is, an exception is raised there, a callable is called, `WAIT` waits on
  the latch (Seam 1: the answer ends only after the disconnect was delivered).
- asgi_call: calls an ASGI app (or a `Response`) directly with a `receive` that gives `http.request` and then
  `http.disconnect` (at once, after the first `delta` sent, or never), scope `asgi.spec_version` "2.3" as with
  uvicorn 0.54 (Seam 1). It returns only when the ASGI call has returned.
- snapshot: every file of a `LocalStorage` root with its bytes.
- logs: every JSON line on stdout (capsys).
"""

from __future__ import annotations

import asyncio
import json
import threading
import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlencode

from thinkhow.access import CurrentUser
from thinkhow.facilitation.types import FacilitationContext, FacilitatorUpdate, MapUpdate, ReplyDelta
from thinkhow.platform.config import load_settings
from thinkhow.platform.identity import IapIdentity
from thinkhow.platform.speech import ScriptedSpeech
from thinkhow.platform.storage import Bucket, LocalStorage
from thinkhow.web.server import Deps, create_app
from thinkhow.workspace import NumberedTurn, TopicRef, create_topic, open_topic, reply, set_language

T0 = datetime(2026, 10, 28, 12, 0, 0, tzinfo=UTC)
ALICE = CurrentUser(id="alice-1", email="alice@example.com", is_owner=False)
IAP = "x-goog-iap-jwt-assertion"
TOKENS: dict[str, dict[str, str]] = {
    "tok-alice": {"sub": "accounts.google.com:alice-1", "email": "alice@example.com"},
}

WAIT = "<wait-for-the-latch>"
LATCH_TIMEOUT = 5.0
AFTER_LATCH_PAUSE = 0.2
READ_ALL_GUARD = 30.0

Mode = Literal["read_all", "disconnect_at_once", "disconnect_after_delta"]


def verify_fake(token: str, audience: str) -> Mapping[str, object]:
    if token not in TOKENS:
        raise RuntimeError("bad signature")
    return TOKENS[token]


class Down(Exception):
    """The facilitator's model failed."""


class Boom(Exception):
    """An exception in the middle of the events."""


def update(reply_text: str, updates: Sequence[dict[str, str]] = ()) -> FacilitatorUpdate:
    return FacilitatorUpdate(
        reply=reply_text,
        current_phase_id="p1",
        phase_exit_met=False,
        map_updates=[MapUpdate.model_validate(u) for u in updates],
    )


Step = str | FacilitatorUpdate | BaseException | Callable[[], None]


@dataclass
class Fac:
    scripts: list[list[Step]] = field(default_factory=list)
    latch: threading.Event = field(default_factory=threading.Event)
    calls: list[FacilitationContext] = field(default_factory=list)
    finished: list[bool] = field(default_factory=list)

    def __call__(self, context: FacilitationContext) -> Iterator[ReplyDelta | FacilitatorUpdate]:
        self.calls.append(context)
        if not self.scripts:
            raise AssertionError("facilitate was called more times than the scenario planned")
        return self._run(self.scripts.pop(0))

    def _run(self, script: list[Step]) -> Iterator[ReplyDelta | FacilitatorUpdate]:
        for step in script:
            if isinstance(step, BaseException):
                raise step
            if isinstance(step, FacilitatorUpdate):
                yield step
            elif step == WAIT:
                self.latch.wait(LATCH_TIMEOUT)
                time.sleep(AFTER_LATCH_PAUSE)
            elif isinstance(step, str):
                yield ReplyDelta(text=step)
            else:
                step()
        self.finished.append(True)


def settings_for(tmp_path: Path) -> Any:
    return load_settings(
        {
            "THINKHOW_LOCAL": "true",
            "THINKHOW_LOCAL_DIR": str(tmp_path),
            "THINKHOW_OWNER_EMAIL": "owner@example.com",
        }
    )


def make_app(tmp_path: Path, storage: LocalStorage, fac: Fac) -> Any:
    deps = Deps(
        storage=storage,
        identity=IapIdentity("aud-test", verify_fake),
        settings=settings_for(tmp_path),
        facilitate=fac,
        now=lambda: T0,
        speech=ScriptedSpeech("(локальний режим) розпізнаний текст"),
    )
    return create_app(deps)


def new_store(tmp_path: Path) -> LocalStorage:
    store = LocalStorage(tmp_path / "data")
    set_language(store, ALICE, "uk-UA")
    return store


def seed_topic(store: LocalStorage, title: str, exchanges: Sequence[tuple[str, str]] = ()) -> TopicRef:
    ref = TopicRef(ALICE.id, create_topic(store, ALICE, title, T0))
    for ask, answer in exchanges:
        list(reply(store, Fac([[answer, update(answer)]]), ALICE, ref, ask, T0))
    return ref


def make_pending(store: LocalStorage, ref: TopicRef, ask: str) -> None:
    """The person's turn saved, the answer failed: the topic awaits an answer."""
    list(reply(store, Fac([[Down("down")]]), ALICE, ref, ask, T0))


def turns(store: LocalStorage, ref: TopicRef) -> list[tuple[int, str, str]]:
    view = open_topic(store, ALICE, ref, T0)
    all_turns: list[NumberedTurn] = [t for s in view.sessions for t in s.turns]
    return [(t.no, t.role, t.text) for t in all_turns]


def snapshot(store: LocalStorage) -> dict[str, bytes]:
    root = store.root
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


@dataclass
class Call:
    messages: list[dict[str, Any]]
    receive_calls: int

    @property
    def start(self) -> dict[str, Any] | None:
        for m in self.messages:
            if m["type"] == "http.response.start":
                return m
        return None

    @property
    def body(self) -> bytes:
        return b"".join(m.get("body", b"") for m in self.messages if m["type"] == "http.response.body")


def scope_for(path: str, body: bytes, extra_headers: Sequence[tuple[bytes, bytes]] = ()) -> dict[str, Any]:
    return {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "root_path": "",
        "headers": [
            (b"host", b"testserver"),
            (b"content-type", b"application/x-www-form-urlencoded"),
            (b"content-length", str(len(body)).encode()),
            (IAP.encode(), b"tok-alice"),
            *extra_headers,
        ],
        "client": ("127.0.0.1", 50000),
        "server": ("testserver", 80),
        "state": {},
    }


def asgi_call(
    app: Any,
    path: str,
    mode: Mode,
    form: Mapping[str, str] | None = None,
    latch: threading.Event | None = None,
    extra_headers: Sequence[tuple[bytes, bytes]] = (),
) -> Call:
    """One ASGI call; returns after the call returned. `latch` is set when the disconnect is delivered."""
    body = urlencode(dict(form or {})).encode()
    scope = scope_for(path, body, extra_headers)
    messages: list[dict[str, Any]] = []
    count = [0]

    async def run() -> None:
        delta_sent = asyncio.Event()
        never = asyncio.Event()

        async def receive() -> dict[str, Any]:
            count[0] += 1
            if count[0] == 1:
                return {"type": "http.request", "body": body, "more_body": False}
            if mode == "read_all":
                try:
                    await asyncio.wait_for(never.wait(), READ_ALL_GUARD)
                except TimeoutError:
                    pass
            if mode == "disconnect_after_delta":
                await delta_sent.wait()
            if latch is not None:
                latch.set()
            return {"type": "http.disconnect"}

        async def send(message: Mapping[str, Any]) -> None:
            messages.append(dict(message))
            if message["type"] == "http.response.body" and b"event: delta" in message.get("body", b""):
                delta_sent.set()

        await app(scope, receive, send)

    asyncio.run(run())
    return Call(messages, count[0])


def sse_events(body: str) -> list[tuple[str, Any]]:
    """Strict: blocks end with an empty line; each block is exactly `event:` and ONE `data:` line of JSON."""
    text = body.replace("\r\n", "\n")
    if not text:
        return []
    assert text.endswith("\n\n"), f"the stream does not end with an empty line: {body!r}"
    events: list[tuple[str, Any]] = []
    for block in text[:-2].split("\n\n"):
        lines = block.split("\n")
        assert len(lines) == 2, f"an event is not exactly `event:` + one `data:` line: {block!r}"
        assert lines[0].startswith("event:") and lines[1].startswith("data:"), block
        name = lines[0][len("event:") :].removeprefix(" ")
        data = json.loads(lines[1][len("data:") :].removeprefix(" "))
        events.append((name, data))
    return events


def log_lines(out: str) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for line in out.splitlines():
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


class StorageBroke(Exception):
    """A failure of the storage in the middle of the stream."""


class ArmedStorage(LocalStorage):
    """A `LocalStorage` whose writes raise `StorageBroke` once `armed` is set."""

    def __init__(self, root: Path) -> None:
        super().__init__(root)
        self.armed = False

    def write(self, bucket: Bucket, path: str, data: bytes, content_type: str) -> None:
        if self.armed:
            raise StorageBroke("disk gone")
        super().write(bucket, path, data, content_type)

    def create_if_absent(self, bucket: Bucket, path: str, data: bytes, content_type: str) -> bool:
        if self.armed:
            raise StorageBroke("disk gone")
        return super().create_if_absent(bucket, path, data, content_type)
