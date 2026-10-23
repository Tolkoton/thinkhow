"""Helpers for the voice-dictation contract tests (slice tester). Built from the contract, not the code.

- RecordingSpeech: a `Speech` double of the tests' own; remembers (audio, mime, language), returns `text`
  or raises `fail`; records whether an event loop was running in the thread that called it (Seam 6).
- make_app: `create_app(Deps(...))` with a local folder, `IapIdentity(verify_fake)` and the given speech.
- FakeGenai: an object with `models.generate_content`; each call takes the next planned step: an exception
  is raised on the call (as the real SDK does), a list of `types.Part` is returned as one candidate.
- LogCapture: the whole text of the journal (log_event's default stream, stdout and stderr).
- FormPage: the tags of a page and, for each tag, whether it stands inside a <form>.
- run_node_test: run ONE named test of a `node --test` file; node missing is a failure.
"""

from __future__ import annotations

import asyncio
import io
import json
import os
import re
import shutil
import subprocess
import threading
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from google.genai import errors, types

from thinkhow.access import CurrentUser
from thinkhow.platform import log
from thinkhow.platform.config import load_settings
from thinkhow.platform.identity import IapIdentity
from thinkhow.platform.speech import Speech
from thinkhow.platform.storage import LocalStorage
from thinkhow.web.server import Deps, create_app
from thinkhow.workspace import TopicRef, create_topic

REPO = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
T0 = datetime(2026, 10, 23, 16, 0, 0, tzinfo=UTC)

ALICE = CurrentUser(id="alice-1", email="alice@example.com", is_owner=False)
BOB = CurrentUser(id="bob_2", email="bob@example.com", is_owner=False)
OWNER = CurrentUser(id="owner-9", email="owner@example.com", is_owner=True)

IAP = "x-goog-iap-jwt-assertion"
TOKENS: dict[str, dict[str, str]] = {
    "tok-alice": {"sub": "accounts.google.com:alice-1", "email": "alice@example.com"},
    "tok-bob": {"sub": "accounts.google.com:bob_2", "email": "bob@example.com"},
    "tok-owner": {"sub": "accounts.google.com:owner-9", "email": "owner@example.com"},
}
H_ALICE = {IAP: "tok-alice"}
H_BOB = {IAP: "tok-bob"}
H_OWNER = {IAP: "tok-owner"}

# The texts of the contract (Q9, Seam 3, S1's NoLanguage fragment).
NOT_ACCEPTED = "Запис не прийнято — спробуйте записати ще раз."
NOT_RECOGNIZED = "Не вдалося розпізнати — спробуйте ще раз."
TOPIC_NOT_FOUND = "Тему не знайдено."
FIRST_CHOOSE = "Спершу оберіть мову (сторінка «Мова»)."
LOCAL_TEXT = "(локальний режим) розпізнаний текст"

AUDIO = b"\x1aE\xdf\xa3 fake webm opus bytes \x00\x01\x02"


def verify_fake(token: str, audience: str) -> Mapping[str, object]:
    if token not in TOKENS:
        raise RuntimeError("bad signature")
    return TOKENS[token]


def _no_facilitate(context: Any) -> Any:
    raise AssertionError("facilitate is not called in voice-dictation tests")


@dataclass
class RecordingSpeech:
    text: str = "розпізнаний текст"
    fail: BaseException | None = None
    calls: list[tuple[bytes, str, str]] = field(default_factory=list)
    loop_running: list[bool] = field(default_factory=list)
    threads: list[threading.Thread] = field(default_factory=list)

    def transcribe(self, audio: bytes, mime: str, language: str) -> str:
        self.calls.append((audio, mime, language))
        self.threads.append(threading.current_thread())
        try:
            asyncio.get_running_loop()
            self.loop_running.append(True)
        except RuntimeError:
            self.loop_running.append(False)
        if self.fail is not None:
            raise self.fail
        return self.text


@dataclass
class App:
    client: TestClient
    storage: LocalStorage


def settings_for(tmp_path: Path) -> Any:
    return load_settings(
        {
            "THINKHOW_LOCAL": "true",
            "THINKHOW_LOCAL_DIR": str(tmp_path),
            "THINKHOW_OWNER_EMAIL": "owner@example.com",
        }
    )


def make_app(tmp_path: Path, speech: Speech) -> App:
    store = LocalStorage(tmp_path / "data")
    deps = Deps(
        storage=store,
        identity=IapIdentity("aud-test", verify_fake),
        settings=settings_for(tmp_path),
        facilitate=_no_facilitate,
        now=lambda: T0,
        speech=speech,
    )
    client = TestClient(create_app(deps), raise_server_exceptions=False, follow_redirects=False)
    return App(client, store)


def new_topic(store: LocalStorage, user: CurrentUser, title: str = "Тема") -> TopicRef:
    return TopicRef(user.id, create_topic(store, user, title, T0))


def voice_url(ref: TopicRef) -> str:
    return f"/topics/{ref.uid}/{ref.topic_id}/voice"


def page_url(ref: TopicRef) -> str:
    return f"/topics/{ref.uid}/{ref.topic_id}"


def snapshot(root: Path) -> dict[str, bytes]:
    """Every file under `root` with its bytes: a write of any kind changes it."""
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def error_fragment(body: str) -> str:
    m = re.fullmatch(r'\s*<p class="error">(.*)</p>\s*', body, flags=re.S)
    assert m, f'the body is not one <p class="error"> fragment: {body!r}'
    return m.group(1)


# ------------------------------------------------------------------ genai


def api_error(code: int) -> errors.APIError:
    body = {"error": {"code": code, "message": f"fake {code}", "status": "FAKE"}}
    if code >= 500:
        return errors.ServerError(code, body)
    return errors.ClientError(code, body)


def response(*parts: types.Part) -> types.GenerateContentResponse:
    return types.GenerateContentResponse(
        candidates=[types.Candidate(content=types.Content(role="model", parts=list(parts)))]
    )


def text_part(text: str, thought: bool = False) -> types.Part:
    return types.Part(text=text, thought=True) if thought else types.Part(text=text)


class FakeModels:
    def __init__(self, plan: list[Any]) -> None:
        self.plan = list(plan)
        self.calls: list[dict[str, Any]] = []

    def generate_content(self, *args: Any, **kwargs: Any) -> types.GenerateContentResponse:
        self.calls.append(kwargs)
        if not self.plan:
            raise AssertionError("the fake client was called more times than the test planned")
        step = self.plan.pop(0)
        if isinstance(step, BaseException):
            raise step
        if isinstance(step, types.GenerateContentResponse):
            return step
        if isinstance(step, str):
            return response(text_part(step))
        return response(*step)


class FakeGenai:
    def __init__(self, plan: list[Any] | None = None, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.models = FakeModels(plan or [])

    @property
    def calls(self) -> list[dict[str, Any]]:
        return self.models.calls


def cfg_get(config: Any, name: str) -> Any:
    if config is None:
        return None
    if isinstance(config, dict):
        return config.get(name)
    return getattr(config, name, None)


class Sleeps:
    def __init__(self) -> None:
        self.delays: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.delays.append(seconds)


class Clock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        self.now += 0.25
        return self.now


# ------------------------------------------------------------------ the journal


class LogCapture:
    def __init__(self, capsys: Any) -> None:
        self.buffer = io.StringIO()
        self.capsys = capsys
        self.printed = ""

    def text(self) -> str:
        out, err = self.capsys.readouterr()
        self.printed += out + err
        return self.buffer.getvalue() + self.printed

    def events(self, name: str) -> list[dict[str, Any]]:
        found: list[dict[str, Any]] = []
        for line in self.text().splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            if isinstance(obj, dict) and obj.get("event") == name:
                found.append(obj)
        return found


def install_log_capture(monkeypatch: pytest.MonkeyPatch, capsys: Any) -> LogCapture:
    cap = LogCapture(capsys)
    monkeypatch.setattr(log.log_event, "__defaults__", (cap.buffer,))
    return cap


# ------------------------------------------------------------------ pages


class FormPage(HTMLParser):
    """Each tag with its attributes, its own text, and whether it stands inside a <form>."""

    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "wbr"}

    def __init__(self, html: str) -> None:
        super().__init__(convert_charrefs=True)
        self.elements: list[dict[str, Any]] = []
        self._open: list[dict[str, Any]] = []
        self.feed(html)
        self.close()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        in_form = any(e["tag"] == "form" for e in self._open)
        el = {"tag": tag, "attrs": dict(attrs), "text": [], "in_form": in_form}
        self.elements.append(el)
        if tag not in self.VOID:
            self._open.append(el)

    def handle_endtag(self, tag: str) -> None:
        for i in range(len(self._open) - 1, -1, -1):
            if self._open[i]["tag"] == tag:
                del self._open[i:]
                return

    def handle_data(self, data: str) -> None:
        for el in self._open:
            el["text"].append(data)

    def by_id(self, el_id: str) -> dict[str, Any] | None:
        found = [e for e in self.elements if e["attrs"].get("id") == el_id]
        assert len(found) <= 1, f"more than one element with id={el_id!r}"
        return found[0] if found else None

    @staticmethod
    def text_of(el: dict[str, Any]) -> str:
        return re.sub(r"\s+", " ", "".join(el["text"])).strip()


# ------------------------------------------------------------------ node --test


def run_node_test(file: Path, name: str) -> None:
    node = os.environ.get("THINKHOW_NODE") or shutil.which("node")
    if not node:
        pytest.fail("node not found on PATH nor in THINKHOW_NODE: the JS seams depend on node --test")
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
