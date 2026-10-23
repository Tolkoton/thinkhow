"""Helpers for the skel-web contract tests (slice tester). Built from the contract, not the code.

- verify_fake / TOKENS: the `verify` of an `IapIdentity`: a known token gives its claims, else raises.
- ScenarioFacilitate: a `Facilitate` double; each call takes the next planned script. A `str` is a
  `ReplyDelta`, a `FacilitatorUpdate` is yielded as is, an exception is raised there, a callable is called.
- ArmedStorage: a `LocalStorage` whose writes raise `StorageBroke` once `armed` is set.
- make_app: `create_app(Deps(...))` with a local folder, the double and `IapIdentity(verify_fake)`.
- choose_language: the persons of a test choose a language before a page is opened (voice-language S1:
  a page without a chosen language is a 303 to `/language`).
- sse_events: a strict reader of a `text/event-stream` body (each event: `event:` + ONE `data:` line + blank).
- Page: the tags and the text of a page (html.parser), the text inside the element with a given id.
- LogCapture: every JSON line written by `log_event` (default stream redirected) or on stdout.
"""

from __future__ import annotations

import io
import json
import os
import re
import shutil
import subprocess
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from thinkhow.access import CurrentUser
from thinkhow.facilitation.types import FacilitationContext, FacilitatorUpdate, MapUpdate, ReplyDelta
from thinkhow.platform import log
from thinkhow.platform.config import load_settings
from thinkhow.platform.identity import IapIdentity
from thinkhow.platform.storage import Bucket, LocalStorage
from thinkhow.web.server import Deps, create_app
from thinkhow.workspace import TopicRef, create_topic, reply, set_language

REPO = Path(__file__).resolve().parents[3]
CARDS = REPO / "cards"
T0 = datetime(2026, 10, 22, 16, 0, 0, tzinfo=UTC)

ALICE = CurrentUser(id="alice-1", email="alice@example.com", is_owner=False)
BOB = CurrentUser(id="bob_2", email="bob@example.com", is_owner=False)
OWNER = CurrentUser(id="owner-9", email="owner@example.com", is_owner=True)

IAP = "x-goog-iap-jwt-assertion"
TOKENS: dict[str, dict[str, str]] = {
    "tok-alice": {"sub": "accounts.google.com:alice-1", "email": "alice@example.com"},
    "tok-bob": {"sub": "accounts.google.com:bob_2", "email": "bob@example.com"},
    # the owner's email in another case than in the settings (Seam 3)
    "tok-owner": {"sub": "accounts.google.com:owner-9", "email": "OWNER@Example.COM"},
}
H_ALICE = {IAP: "tok-alice"}
H_BOB = {IAP: "tok-bob"}
H_OWNER = {IAP: "tok-owner"}


def verify_fake(token: str, audience: str) -> Mapping[str, object]:
    if token not in TOKENS:
        raise RuntimeError("bad signature")
    return TOKENS[token]


class Boom(Exception):
    """A failure of the model in the middle of the deltas (Seam 2)."""


class StorageBroke(Exception):
    """A failure of the storage in the middle of the stream."""


class ArmedStorage(LocalStorage):
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


class ListBroken(LocalStorage):
    def list(self, bucket: Bucket, prefix: str) -> list[str]:
        raise RuntimeError("boom-internal-detail")


def update(reply_text: str, updates: list[dict[str, str]] | None = None) -> FacilitatorUpdate:
    return FacilitatorUpdate(
        reply=reply_text,
        current_phase_id="p1",
        phase_exit_met=False,
        map_updates=[MapUpdate.model_validate(u) for u in (updates or [])],
    )


Step = str | FacilitatorUpdate | BaseException | Callable[[], None]


@dataclass
class ScenarioFacilitate:
    scripts: list[list[Step]] = field(default_factory=list)
    calls: list[FacilitationContext] = field(default_factory=list)

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
            elif isinstance(step, str):
                yield ReplyDelta(text=step)
            else:
                step()


def settings_for(tmp_path: Path, owner_email: str = "owner@example.com") -> Any:
    return load_settings(
        {
            "THINKHOW_LOCAL": "true",
            "THINKHOW_LOCAL_DIR": str(tmp_path),
            "THINKHOW_OWNER_EMAIL": owner_email,
        }
    )


@dataclass
class App:
    client: TestClient
    storage: LocalStorage
    fac: ScenarioFacilitate


def make_app(
    tmp_path: Path,
    scripts: list[list[Step]] | None = None,
    storage: LocalStorage | None = None,
    now: Callable[[], datetime] = lambda: T0,
) -> App:
    store = storage if storage is not None else LocalStorage(tmp_path / "data")
    fac = ScenarioFacilitate(list(scripts or []))
    deps = Deps(
        storage=store,
        identity=IapIdentity("aud-test", verify_fake),
        settings=settings_for(tmp_path),
        facilitate=fac,
        now=now,
    )
    client = TestClient(create_app(deps), raise_server_exceptions=False, follow_redirects=False)
    return App(client, store, fac)


def choose_language(storage: LocalStorage, *users: CurrentUser, code: str = "uk-UA") -> None:
    """Each person has chosen a language, as `POST /language` would record it (voice-language S1)."""
    for user in users:
        set_language(storage, user, code)


def seed_topic(
    store: LocalStorage,
    user: CurrentUser,
    title: str,
    exchanges: Sequence[tuple[str, str]] = (),
) -> TopicRef:
    """A topic of `user` made through workspace itself, with answered exchanges (person, facilitator)."""
    ref = TopicRef(user.id, create_topic(store, user, title, T0))
    for ask, answer in exchanges:
        fac = ScenarioFacilitate([[answer, update(answer)]])
        list(reply(store, fac, user, ref, ask, T0))
    return ref


def make_pending(store: LocalStorage, user: CurrentUser, ref: TopicRef, ask: str) -> None:
    """The person's turn saved, the answer failed: the topic is awaiting an answer."""
    fac = ScenarioFacilitate([[Boom("down")]])
    list(reply(store, fac, user, ref, ask, T0))


def conv(store: LocalStorage, ref: TopicRef) -> bytes | None:
    return store.read("users", f"{ref.uid}/{ref.topic_id}/conversation.md")


def sse_events(body: str) -> list[tuple[str, Any]]:
    """Strict: blocks end with an empty line; each block is exactly `event:` and ONE `data:` line of JSON."""
    text = body.replace("\r\n", "\n")
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


def error_fragment(body: str) -> str:
    """The text of the one `<p class="error">…</p>` fragment the body must be."""
    m = re.fullmatch(r'\s*<p class="error">(.*)</p>\s*', body, flags=re.S)
    assert m, f'the body is not one <p class="error"> fragment: {body!r}'
    return Page(f"<div id='x'>{m.group(1)}</div>").text_of("x")


class Page(HTMLParser):
    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "wbr"}

    def __init__(self, html: str) -> None:
        super().__init__(convert_charrefs=True)
        self.tags: list[tuple[str, dict[str, str | None]]] = []
        self._texts: dict[str, list[str]] = {}
        self._open: list[tuple[str, str | None]] = []
        self.all_text: list[str] = []
        self.script_texts: list[str] = []
        self.feed(html)
        self.close()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        self.tags.append((tag, a))
        if tag in self.VOID:
            return
        el_id = a.get("id")
        if el_id is not None:
            self._texts.setdefault(el_id, [])
        self._open.append((tag, el_id))

    def handle_endtag(self, tag: str) -> None:
        for i in range(len(self._open) - 1, -1, -1):
            if self._open[i][0] == tag:
                del self._open[i:]
                return

    def handle_data(self, data: str) -> None:
        self.all_text.append(data)
        if self._open and self._open[-1][0] == "script":
            self.script_texts.append(data)
        for _, el_id in self._open:
            if el_id is not None:
                self._texts[el_id].append(data)

    def has_id(self, el_id: str) -> bool:
        return el_id in self._texts

    def text_of(self, el_id: str) -> str:
        assert el_id in self._texts, f"no element with id={el_id!r}"
        return "".join(self._texts[el_id])

    def text(self) -> str:
        return "".join(self.all_text)

    def shows(self, needle: str) -> bool:
        """In the text outside <script>, or in an attribute value (a button may be <input value=…>)."""
        visible = self.text()
        for chunk in self.script_texts:
            visible = visible.replace(chunk, "", 1)
        return needle in visible or any(needle in (v or "") for _, a in self.tags for v in a.values())

    def has_tag(self, tag: str, **attrs: str) -> bool:
        return any(t == tag and all(a.get(k) == v for k, v in attrs.items()) for t, a in self.tags)


class LogCapture:
    def __init__(self, capsys: Any) -> None:
        self.buffer = io.StringIO()
        self.capsys = capsys
        self._out = ""

    def lines(self) -> list[dict[str, Any]]:
        self._out += self.capsys.readouterr().out
        raw = self.buffer.getvalue() + "\n" + self._out
        found: list[dict[str, Any]] = []
        for line in raw.splitlines():
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


def run_node_test(file: Path, name: str) -> None:
    """Run ONE named test of a `node --test` file; node missing is a failure, never a skip (Seam 5)."""
    node = os.environ.get("THINKHOW_NODE") or shutil.which("node")
    if not node:
        pytest.fail(
            "node not found on PATH nor in THINKHOW_NODE: the exit of skel-web depends on node --test"
        )
    pattern = "^" + re.escape(name) + "$"
    proc = subprocess.run(
        [node, "--test", "--test-reporter=tap", f"--test-name-pattern={pattern}", str(file)],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=REPO,
    )
    out = proc.stdout + proc.stderr
    assert proc.returncode == 0 and "# pass 1" in out and "# fail 0" in out, out
