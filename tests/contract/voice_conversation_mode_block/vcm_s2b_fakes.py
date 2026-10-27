"""Helpers for the voice block tests with S2b in place (slice tester, mode `block`). Written from
`.engine/architecture/feature/voice-conversation-mode.md` and the public signatures.

- serve_s2b(): the REAL app (`build_deps` in local mode + `create_app`) under a real uvicorn in a thread, with
  the port doubles a test needs: a recognition that answers a planned sequence (text or failure), a synthesis
  that fails on chosen calls, a facilitate that fails on chosen attempts.
- run_s2b_page(): the REAL `conversation.js` in the S2b page fakes, its /voice, /reply, /retry, /speak sent to
  that server (`vcm_s2b_page.mjs`).
"""

from __future__ import annotations

import dataclasses
import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
import pytest
import uvicorn
from vcm_fakes import RecordingFacilitate, RecordingTts, Server, _free_port

from thinkhow.facilitation.types import FacilitationContext, FacilitatorUpdate, ReplyDelta
from thinkhow.platform.speech import SpeechUnavailable
from thinkhow.platform.tts import TtsUnavailable
from thinkhow.web.app import CARDS_DIR, build_deps
from thinkhow.web.server import create_app

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
DRIVER = HERE / "vcm_s2b_page.mjs"

FAIL = object()  # in a PlannedSpeech plan: this recognition fails


@dataclass
class PlannedSpeech:
    """Recognition that answers the planned texts in order; FAIL raises the port's own exception."""

    plan: Sequence[Any]
    calls: int = 0

    def transcribe(self, audio: bytes, mime: str, language: str, vocabulary: Sequence[str] = ()) -> str:
        item = self.plan[min(self.calls, len(self.plan) - 1)]
        self.calls += 1
        if item is FAIL:
            raise SpeechUnavailable("recognition failed (test)")
        return str(item)


@dataclass
class FailingAt:
    """Synthesis that wraps the app's own and fails (the port's exception) on the given calls (0-based)."""

    inner: Any
    fail_at: set[int]
    calls: list[tuple[str, str]] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)

    def synthesize(self, text: str, language: str) -> bytes:
        n = len(self.calls)
        self.calls.append((text, language))
        if n in self.fail_at:
            self.failed.append(text)
            raise TtsUnavailable("synthesis failed (test)")
        audio: bytes = self.inner.synthesize(text, language)
        return audio


def attempts(answers: Sequence[Sequence[str] | None]) -> Callable[[FacilitationContext], Iterator[Any]]:
    """A facilitate written by hand: attempt i streams the deltas answers[i] and settles on their sum;
    None makes that attempt fail mid-way. After the plan, the last entry repeats."""
    count = {"n": 0}

    def facilitate(ctx: FacilitationContext) -> Iterator[Any]:
        plan = answers[min(count["n"], len(answers) - 1)]
        count["n"] += 1
        if plan is None:
            yield ReplyDelta("Привіт, ти зна")
            raise RuntimeError("the model failed (test)")
        for d in plan:
            yield ReplyDelta(d)
        yield FacilitatorUpdate(
            reply="".join(plan), current_phase_id=None, phase_exit_met=False, map_updates=[]
        )

    return facilitate


@contextmanager
def serve_s2b(speech: Any = None, tts: Any = None, facilitate: Any = None) -> Iterator[tuple[Server, Any]]:
    data = tempfile.mkdtemp(prefix="vcm-s2b-")
    env = {"THINKHOW_LOCAL": "true", "THINKHOW_LOCAL_DIR": data, "THINKHOW_OWNER_EMAIL": "owner@localhost"}
    deps = build_deps(env, CARDS_DIR)
    the_tts = tts(deps.tts) if callable(tts) else RecordingTts(deps.tts)
    rec_fac = RecordingFacilitate(facilitate if facilitate is not None else deps.facilitate)
    replace: dict[str, Any] = {"tts": the_tts, "facilitate": rec_fac}
    if speech is not None:
        replace["speech"] = speech
    deps = dataclasses.replace(deps, **replace)
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
            yield Server(base, the_tts, rec_fac, http, None), deps.speech
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        shutil.rmtree(data, ignore_errors=True)


def run_s2b_page(server: Server, prefix: str, turns: int) -> dict[str, Any]:
    node = os.environ.get("THINKHOW_NODE") or shutil.which("node")
    if not node:
        pytest.fail("node not found on PATH nor in THINKHOW_NODE: these tests need node")
    cfg = {"base": server.base, "prefix": prefix, "turns": turns}
    proc = subprocess.run(
        [node, str(DRIVER), json.dumps(cfg)], capture_output=True, text=True, timeout=180, cwd=REPO
    )
    line = next((x for x in proc.stdout.splitlines() if x.startswith("VCM_RESULT ")), None)
    assert line, proc.stdout + proc.stderr
    result: dict[str, Any] = json.loads(line.removeprefix("VCM_RESULT "))
    assert not result["problems"], result["problems"]
    assert not result["other_calls"], result["other_calls"]
    return result
