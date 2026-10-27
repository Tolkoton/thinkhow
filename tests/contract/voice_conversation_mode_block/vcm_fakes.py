"""Helpers for the voice-conversation-mode block (integration) tests. Slice tester, mode `block`; written from
`.engine/architecture/feature/voice-conversation-mode.md` («Inter-slice contracts») and the public signatures.

- serve(): the REAL app (`build_deps` in local mode + `create_app`) under a real uvicorn in a thread;
  `tts` and `facilitate` are wrapped by recorders of the tests' own (or replaced by given ones).
- run_page(): the REAL `conversation.js` in the page fakes, its /voice, /reply, /speak sent to that server
  (`vcm_page.mjs`); returns what the page did and what the server answered it.
"""

from __future__ import annotations

import dataclasses
import functools
import json
import os
import re
import shutil
import socket
import subprocess
import tempfile
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
import pytest
import uvicorn

from thinkhow.facilitation.types import FacilitationContext, FacilitatorUpdate, ReplyDelta
from thinkhow.platform.tts import Tts, TtsUnavailable
from thinkhow.web.app import CARDS_DIR, build_deps
from thinkhow.web.server import create_app

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
DRIVER = HERE / "vcm_page.mjs"


@dataclass
class RecordingTts:
    """Wraps the app's own TTS: remembers (text, language) and the bytes it returned."""

    inner: Tts
    calls: list[tuple[str, str]] = field(default_factory=list)
    returned: list[bytes] = field(default_factory=list)

    def synthesize(self, text: str, language: str) -> bytes:
        self.calls.append((text, language))
        audio = self.inner.synthesize(text, language)
        self.returned.append(audio)
        return audio


@dataclass
class FailingTts:
    """Synthesis that never gives audio (the port's own exception)."""

    calls: list[tuple[str, str]] = field(default_factory=list)

    def synthesize(self, text: str, language: str) -> bytes:
        self.calls.append((text, language))
        raise TtsUnavailable("synthesis failed (test)")


@dataclass
class RecordingLlm:
    """Wraps the app's own model: remembers every system instruction it is given."""

    inner: Any
    systems: list[str] = field(default_factory=list)

    def stream_json(self, system: str, contents: Any, schema: Any, rev: Any) -> Iterator[Any]:
        self.systems.append(system)
        yield from self.inner.stream_json(system, contents, schema, rev)

    def generate_json(self, system: str, contents: Any, schema: Any, rev: Any) -> Any:
        self.systems.append(system)
        return self.inner.generate_json(system, contents, schema, rev)

    def search_text(self, system: str, prompt: str, rev: Any) -> Any:
        self.systems.append(system)
        return self.inner.search_text(system, prompt, rev)


@dataclass
class RecordingFacilitate:
    """Wraps the app's own facilitate: remembers every FacilitationContext it is given."""

    inner: Callable[[FacilitationContext], Iterator[Any]]
    contexts: list[FacilitationContext] = field(default_factory=list)

    def __call__(self, ctx: FacilitationContext) -> Iterator[Any]:
        self.contexts.append(ctx)
        yield from self.inner(ctx)


def answering(text: str) -> Callable[[FacilitationContext], Iterator[Any]]:
    """A facilitate written by hand that answers `text` once."""

    def facilitate(ctx: FacilitationContext) -> Iterator[Any]:
        yield ReplyDelta(text)
        yield FacilitatorUpdate(reply=text, current_phase_id=None, phase_exit_met=False, map_updates=[])

    return facilitate


@dataclass
class Server:
    base: str
    tts: Any
    facilitate: RecordingFacilitate
    http: httpx.Client
    llm: RecordingLlm | None = None

    def choose(self, code: str) -> None:
        r = self.http.post("/language", data={"code": code})
        assert r.status_code in (200, 303), (r.status_code, r.text)

    def new_topic(self, title: str = "Тема") -> str:
        r = self.http.post("/topics", data={"title": title})
        assert r.status_code == 303, (r.status_code, r.text)
        return str(r.headers["location"])

    def reply_form(self, topic: str) -> dict[str, str]:
        """The attributes of the real `<form id="reply-form" …>` of the topic page."""
        html = self.http.get(topic).text
        m = re.search(r"<form\b[^>]*\bid=\"reply-form\"[^>]*>", html, re.S)
        assert m, "no #reply-form on the topic page"
        return dict(re.findall(r"([\w-]+)=\"([^\"]*)\"", m.group(0)))


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@contextmanager
def serve(tts: Any = None, facilitate: Any = None) -> Iterator[Server]:
    data = tempfile.mkdtemp(prefix="vcm-block-")
    env = {"THINKHOW_LOCAL": "true", "THINKHOW_LOCAL_DIR": data, "THINKHOW_OWNER_EMAIL": "owner@localhost"}
    deps = build_deps(env, CARDS_DIR)
    rec_tts = tts if tts is not None else RecordingTts(deps.tts)
    inner = facilitate if facilitate is not None else deps.facilitate
    rec_llm = None
    if facilitate is None and isinstance(inner, functools.partial) and "llm" in inner.keywords:
        rec_llm = RecordingLlm(inner.keywords["llm"])  # the app's own facilitate, its model recorded
        inner = functools.partial(inner.func, *inner.args, **{**inner.keywords, "llm": rec_llm})
    rec_fac = RecordingFacilitate(inner)
    deps = dataclasses.replace(deps, tts=rec_tts, facilitate=rec_fac)
    port = _free_port()
    config = uvicorn.Config(
        create_app(deps), host="127.0.0.1", port=port, log_level="warning", lifespan="off"
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    end = time.monotonic() + 20
    while not server.started:
        assert time.monotonic() < end, "uvicorn did not start"
        time.sleep(0.02)
    base = f"http://127.0.0.1:{port}"
    try:
        with httpx.Client(base_url=base, follow_redirects=False, timeout=30) as http:
            yield Server(base, rec_tts, rec_fac, http, rec_llm)
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        shutil.rmtree(data, ignore_errors=True)


def page_prefix(form: dict[str, str]) -> str:
    """`data-key="draft:<uid>/<topic>"` of the real form → `/topics/<uid>/<topic>`."""
    key = form["data-key"]
    assert key.startswith("draft:"), key
    return "/topics/" + key.removeprefix("draft:")


def run_page(server: Server, prefix: str, voice: str, **flags: Any) -> dict[str, Any]:
    node = os.environ.get("THINKHOW_NODE") or shutil.which("node")
    if not node:
        pytest.fail("node not found on PATH nor in THINKHOW_NODE: these tests need node")
    cfg = {"base": server.base, "prefix": prefix, "voice": voice, **flags}
    proc = subprocess.run(
        [node, str(DRIVER), json.dumps(cfg)], capture_output=True, text=True, timeout=120, cwd=REPO
    )
    line = next((x for x in proc.stdout.splitlines() if x.startswith("VCM_RESULT ")), None)
    assert line, proc.stdout + proc.stderr
    result: dict[str, Any] = json.loads(line.removeprefix("VCM_RESULT "))
    assert not result["problems"], result["problems"]
    assert not result["other_calls"], result["other_calls"]
    return result


def of_kind(result: dict[str, Any], kind: str) -> list[dict[str, Any]]:
    return [f for f in result["forwarded"] if f["kind"] == kind]


def deduped(states: list[str]) -> list[str]:
    out: list[str] = []
    for s in states:
        if not out or out[-1] != s:
            out.append(s)
    return out


UKRAINIAN = "uk-UA"
POLISH = "pl-PL"
NO_VOICE = "mt-MT"  # Maltese: in the profile's languages, Google has no voice for it (PR-23: 15 such)
LISTENING_OR_OFF = ("listening", "", "off")


@dataclass
class Turn:
    page: dict[str, Any]
    tts_calls: list[tuple[str, str]]
    tts_returned: list[bytes]
    spoken: list[bool]
    texts: list[str]
    systems: list[str]


@functools.cache
def one_turn() -> Turn:
    """Ukrainian, one tap, one spoken turn against the real server, all sentences played, a second tap."""
    with serve() as server:
        server.choose(UKRAINIAN)
        form = server.reply_form(server.new_topic())
        page = run_page(server, page_prefix(form), form["data-voice"], tap=True, turn=True, secondTap=True)
        return Turn(
            page,
            list(server.tts.calls),
            list(server.tts.returned),
            [c.spoken for c in server.facilitate.contexts],
            [c.text for c in server.facilitate.contexts],
            list(server.llm.systems) if server.llm else [],
        )


def words(text: str) -> list[str]:
    return re.findall(r"\w+", text)
