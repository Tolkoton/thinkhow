"""Helpers for the voice-synthesis contract tests (slice tester). Built from the contract, not the code.

- FakePost: a `post(url, headers, json, timeout)` double; each call takes the next planned step (an exception
  is raised, an int status or a (status, json) pair becomes an `httpx.Response` with its request attached).
- Tokens: a `token()` double that counts its calls, or raises.
- Sleeps, Clock: the injected `sleep` and `clock`.
- LogCapture: the `tts_call` lines of the journal (log_event's default stream, stdout and stderr).
- make_app: `create_app(Deps(...))` with a local folder, `IapIdentity(verify_fake)` and the given tts.
"""

from __future__ import annotations

import io
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from google.auth.exceptions import GoogleAuthError

from thinkhow.access import CurrentUser
from thinkhow.platform import log
from thinkhow.platform.config import load_settings
from thinkhow.platform.identity import IapIdentity
from thinkhow.platform.speech import ScriptedSpeech
from thinkhow.platform.storage import LocalStorage
from thinkhow.platform.tts import CloudTts, Tts
from thinkhow.web.server import Deps, create_app
from thinkhow.workspace import TopicRef, create_topic

T0 = datetime(2026, 10, 27, 9, 0, 0, tzinfo=UTC)
ENDPOINT = "https://eu-texttospeech.googleapis.com"
URL = "https://eu-texttospeech.googleapis.com/v1/text:synthesize"

# MP3-like bytes and their base64, written by hand.
MP3 = b"ID3\x04\x00fake-mp3"
MP3_B64 = "SUQzBABmYWtlLW1wMw=="

ALICE = CurrentUser(id="alice-1", email="alice@example.com", is_owner=False)
IAP = "x-goog-iap-jwt-assertion"
TOKENS: dict[str, dict[str, str]] = {
    "tok-alice": {"sub": "accounts.google.com:alice-1", "email": "alice@example.com"},
}
H_ALICE = {IAP: "tok-alice"}

# The texts of the contract.
NO_VOICE_TEXT = "There is no voice for your language."
NOT_ACCEPTED_TEXT = "Текст для голосу не прийнято."
UNAVAILABLE_TEXT = "Не вдалося озвучити — спробуйте ще раз."
FIRST_CHOOSE = "Спершу оберіть мову (сторінка «Мова»)."


class FakePost:
    def __init__(self, plan: list[Any]) -> None:
        self.plan = list(plan)
        self.calls: list[dict[str, Any]] = []

    def __call__(
        self, url: Any, headers: Any = None, json: Any = None, timeout: Any = None, **kw: Any
    ) -> Any:
        self.calls.append({"url": str(url), "headers": dict(headers or {}), "json": json, "timeout": timeout})
        if not self.plan:
            raise AssertionError("post was called more times than the test planned")
        step = self.plan.pop(0)
        if isinstance(step, BaseException):
            raise step
        request = httpx.Request("POST", str(url))
        if isinstance(step, int):
            return httpx.Response(step, json={"error": {"code": step}}, request=request)
        status, body = step
        return httpx.Response(status, json=body, request=request)


def ok() -> tuple[int, dict[str, str]]:
    return (200, {"audioContent": MP3_B64})


class Tokens:
    def __init__(self, value: str = "tok-adc-1", fail: BaseException | None = None) -> None:
        self.value = value
        self.fail = fail
        self.calls = 0

    def __call__(self) -> str:
        self.calls += 1
        if self.fail is not None:
            raise self.fail
        return self.value


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


def cloud(
    post: FakePost,
    token: Any = None,
    voice_name: str = "Kore",
    attempts: int = 3,
    sleeps: Sleeps | None = None,
) -> CloudTts:
    return CloudTts(
        post,
        token or Tokens(),
        ENDPOINT,
        voice_name,
        30.0,
        attempts,
        sleep=sleeps if sleeps is not None else Sleeps(),
        clock=Clock(),
    )


def header(headers: Mapping[str, str], name: str) -> str | None:
    for k, v in headers.items():
        if k.lower() == name.lower():
            return v
    return None


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

    def lines(self, name: str) -> list[str]:
        found: list[str] = []
        for line in self.text().splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            if isinstance(obj, dict) and obj.get("event") == name:
                found.append(line)
        return found

    def events(self, name: str) -> list[dict[str, Any]]:
        return [json.loads(line) for line in self.lines(name)]


def install_log_capture(monkeypatch: pytest.MonkeyPatch, capsys: Any) -> LogCapture:
    cap = LogCapture(capsys)
    monkeypatch.setattr(log.log_event, "__defaults__", (cap.buffer,))
    return cap


# ------------------------------------------------------------------ the web


def verify_fake(token: str, audience: str) -> Mapping[str, object]:
    if token not in TOKENS:
        raise RuntimeError("bad signature")
    return TOKENS[token]


def _no_facilitate(context: Any) -> Any:
    raise AssertionError("facilitate is not called in voice-synthesis tests")


@dataclass
class App:
    client: TestClient
    storage: LocalStorage


def local_settings(tmp_path: Path) -> Any:
    return load_settings(
        {
            "THINKHOW_LOCAL": "true",
            "THINKHOW_LOCAL_DIR": str(tmp_path),
            "THINKHOW_OWNER_EMAIL": "owner@example.com",
        }
    )


def make_app(tmp_path: Path, tts: Tts | None = None) -> App:
    store = LocalStorage(tmp_path / "data")
    kwargs: dict[str, Any] = {}
    if tts is not None:
        kwargs["tts"] = tts
    deps = Deps(
        storage=store,
        identity=IapIdentity("aud-test", verify_fake),
        settings=local_settings(tmp_path),
        facilitate=_no_facilitate,
        now=lambda: T0,
        speech=ScriptedSpeech("текст"),
        **kwargs,
    )
    client = TestClient(create_app(deps), raise_server_exceptions=False, follow_redirects=False)
    return App(client, store)


def new_topic(store: LocalStorage, user: CurrentUser, title: str = "Тема") -> TopicRef:
    return TopicRef(user.id, create_topic(store, user, title, T0))


def page_url(ref: TopicRef) -> str:
    return f"/topics/{ref.uid}/{ref.topic_id}"


def snapshot(root: Path) -> dict[str, bytes]:
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


class Tags(HTMLParser):
    def __init__(self, html: str) -> None:
        super().__init__(convert_charrefs=True)
        self.tags: list[tuple[str, dict[str, str | None]]] = []
        self.feed(html)
        self.close()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append((tag, dict(attrs)))

    def by_id(self, el_id: str) -> tuple[str, dict[str, str | None]]:
        found = [t for t in self.tags if t[1].get("id") == el_id]
        assert len(found) == 1, f"expected one element with id={el_id!r}, found {len(found)}"
        return found[0]


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s)


def auth_error() -> GoogleAuthError:
    error: Any = GoogleAuthError  # google-auth's __init__ is untyped
    made: GoogleAuthError = error("no adc")
    return made
