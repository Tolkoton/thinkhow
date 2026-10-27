"""Helper for the spoken-replies catch-up tests of the smoke script (slice tester), from the contract.

The contract («Exit criterion», Smoke): `uv run python scripts/smoke_test_spoken_replies.py` — у процесі,
як `scripts/smoke_test_skel_learning.py`: `TestClient(create_app(deps))`, де `deps` — `build_deps`
локального режиму з `facilitate`, зібраною з тим самим `respond` і сценарною моделлю, обгорнутою
записувачем `system` кожного виклику (обгортка — у скрипті, не в `src/`). `POST /reply` з `spoken=1` і без
нього → 200 SSE `answered` в обох; у записаних `system` розділ «# Людина слухає» є з `spoken=1` і немає без
нього. Справжнього uvicorn тут немає.

`run_smoke` runs the script in-process (runpy, as `__main__`) from the repository root. It watches
`build_deps` and `create_app` (wrapped in place on their modules, so an import of either by name inside the
script gets the watcher) and puts an ASGI middleware around every app `create_app` makes. The middleware
records each request (method, path, form fields, status, body) and, for a «fails when» test, changes ONE
thing: the answer of a `/reply` (status, or the event `answered` blanked out), or the request the server
receives (the `spoken` field hidden, or `spoken=1` forced). Requests are picked by what they carry, never by
the order of the smoke's steps. `subprocess.Popen` is watched too: the contract says there is no uvicorn.
"""

from __future__ import annotations

import io
import os
import re
import runpy
import subprocess
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode

import pytest

import thinkhow.web as web_pkg
import thinkhow.web.app as app_module
import thinkhow.web.server as server_module

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "scripts" / "smoke_test_spoken_replies.py"

ANSWERED = b"event: answered"


@dataclass
class Seen:
    method: str
    path: str
    fields: dict[str, list[str]]
    status: int = 0
    body: bytes = b""

    @property
    def is_reply(self) -> bool:
        return self.method == "POST" and self.path.rstrip("/").endswith("/reply")

    @property
    def spoken(self) -> list[str]:
        return self.fields.get("spoken", [])


@dataclass
class Run:
    ok: bool
    out: str
    seen: list[Seen] = field(default_factory=list)
    built: list[tuple[dict[str, str], Any]] = field(default_factory=list)
    apps: list[Any] = field(default_factory=list)
    launches: list[list[str]] = field(default_factory=list)
    rewritten: int = 0

    def replies(self) -> list[Seen]:
        return [s for s in self.seen if s.is_reply]


@dataclass(frozen=True)
class Sabotage:
    """One change. `answer_for` picks the /reply answers to change: "spoken" (spoken=1), "plain" (not)."""

    answer_for: str | None = None
    new_status: int | None = None
    blank_answered: bool = False
    hide_spoken: bool = False
    force_spoken: bool = False


def _fields(headers: dict[bytes, bytes], body: bytes) -> dict[str, list[str]]:
    ctype = headers.get(b"content-type", b"").decode("latin-1")
    out: dict[str, list[str]] = {}
    if ctype.startswith("application/x-www-form-urlencoded"):
        for key, value in parse_qsl(body.decode("utf-8", "replace"), keep_blank_values=True):
            out.setdefault(key, []).append(value)
    elif ctype.startswith("multipart/form-data"):
        for name, value in re.findall(
            rb'name="([^"]+)"(?:[^\r\n]*)\r\n(?:[^\r\n]+\r\n)*\r\n(.*?)\r\n--', body, re.S
        ):
            out.setdefault(name.decode(), []).append(value.decode("utf-8", "replace"))
    return out


def _force_spoken(headers: dict[bytes, bytes], body: bytes) -> bytes:
    ctype = headers.get(b"content-type", b"").decode("latin-1")
    if ctype.startswith("application/x-www-form-urlencoded"):
        pairs = [(k, v) for k, v in parse_qsl(body.decode("utf-8"), keep_blank_values=True) if k != "spoken"]
        return urlencode([*pairs, ("spoken", "1")]).encode()
    if ctype.startswith("multipart/form-data"):
        boundary = ctype.split("boundary=", 1)[1].strip().strip('"').encode()
        body = re.sub(rb'name="spoken"', b'name="xpoken"', body)
        part = b"--" + boundary + b'\r\nContent-Disposition: form-data; name="spoken"\r\n\r\n1\r\n'
        end = body.rfind(b"--" + boundary + b"--")
        return body[:end] + part + body[end:]
    return body


class _State:
    def __init__(self, sabotage: Sabotage) -> None:
        self.sabotage = sabotage
        self.seen: list[Seen] = []
        self.rewritten = 0


def _middleware(state: _State) -> Any:
    class Watch:
        def __init__(self, app: Any) -> None:
            self.app = app

        async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
            if scope.get("type") != "http":
                await self.app(scope, receive, send)
                return
            chunks: list[bytes] = []
            while True:
                message = await receive()
                if message["type"] != "http.request":
                    break
                chunks.append(message.get("body", b""))
                if not message.get("more_body", False):
                    break
            body = b"".join(chunks)
            headers = {k.lower(): v for k, v in scope.get("headers", [])}
            seen = Seen(
                method=scope.get("method", ""), path=scope.get("path", ""), fields=_fields(headers, body)
            )
            state.seen.append(seen)
            sab = state.sabotage
            if seen.is_reply and sab.hide_spoken and b"spoken" in body:
                body = body.replace(b"spoken", b"xpoken")
                state.rewritten += 1
            if seen.is_reply and sab.force_spoken and seen.spoken != ["1"]:
                body = _force_spoken(headers, body)
                state.rewritten += 1
            new_headers = [(k, v) for k, v in scope.get("headers", []) if k.lower() != b"content-length"]
            new_headers.append((b"content-length", str(len(body)).encode()))
            scope = {**scope, "headers": new_headers}
            sent = False

            async def replay() -> Any:
                nonlocal sent
                if not sent:
                    sent = True
                    return {"type": "http.request", "body": body, "more_body": False}
                return await receive()  # after the body: the client's own (a disconnect only when it goes)

            held: list[Any] = []

            async def keep(message: Any) -> None:
                held.append(message)

            await self.app(scope, replay, keep)
            start = next(m for m in held if m["type"] == "http.response.start")
            out = b"".join(m.get("body", b"") for m in held if m["type"] == "http.response.body")
            status = start["status"]
            picked = (
                sab.answer_for is not None
                and seen.is_reply
                and ((seen.spoken == ["1"]) == (sab.answer_for == "spoken"))
            )
            if picked:
                if sab.new_status is not None:
                    status = sab.new_status
                    state.rewritten += 1
                if sab.blank_answered and ANSWERED in out:
                    out = out.replace(ANSWERED, b"event: XXXXXXXX")
                    state.rewritten += 1
            seen.status = status
            seen.body = out
            await send({**start, "status": status})
            await send({"type": "http.response.body", "body": out, "more_body": False})

    return Watch


def run_smoke(sabotage: Sabotage | None = None) -> Run:
    state = _State(sabotage or Sabotage())
    built: list[tuple[dict[str, str], Any]] = []
    apps: list[Any] = []
    launches: list[list[str]] = []
    real_build = app_module.build_deps
    real_create = server_module.create_app
    real_popen = subprocess.Popen

    def build_deps(environ: Any, *args: Any, **kwargs: Any) -> Any:
        deps = real_build(environ, *args, **kwargs)
        built.append(({str(k): str(v) for k, v in dict(environ).items()}, deps))
        return deps

    def create_app(deps: Any) -> Any:
        app = real_create(deps)
        app.add_middleware(_middleware(state))
        apps.append(deps)
        return app

    def popen(args: Any, *rest: Any, **kwargs: Any) -> Any:
        launches.append(args.split() if isinstance(args, str) else [os.fsdecode(a) for a in args])
        return real_popen(args, *rest, **kwargs)

    out = io.StringIO()
    ok = True
    with pytest.MonkeyPatch.context() as m:
        m.setattr(app_module, "build_deps", build_deps)
        m.setattr(server_module, "create_app", create_app)
        if hasattr(web_pkg, "create_app"):
            m.setattr(web_pkg, "create_app", create_app)
        if hasattr(web_pkg, "build_deps"):
            m.setattr(web_pkg, "build_deps", build_deps)
        m.setattr(subprocess, "Popen", popen)
        m.chdir(REPO)
        try:
            with redirect_stdout(out), redirect_stderr(out):
                runpy.run_path(str(SCRIPT), run_name="__main__")
        except SystemExit as stop:
            ok = stop.code in (0, None)
        except Exception as error:  # an assertion or any error of the smoke is its failure
            out.write(f"\n{type(error).__name__}: {error}")
            ok = False
    return Run(
        ok=ok,
        out=out.getvalue(),
        seen=state.seen,
        built=built,
        apps=apps,
        launches=launches,
        rewritten=state.rewritten,
    )


@cache
def clean_run() -> Run:
    return run_smoke()


def app_served(run: Run) -> None:
    assert run.apps, "the smoke never called thinkhow.web.server.create_app\n" + run.out
    assert run.replies(), "no POST …/reply reached the app create_app made\n" + run.out
