"""Helper for the voice-synthesis catch-up tests of the smoke script (slice tester), from the contract.

The contract («Exit criterion»): `uv run python scripts/smoke_test_voice_synthesis.py` — справжній uvicorn у
локальному режимі: мова `uk-UA` → тема → сторінка має `data-voice="yes"` → `POST /speak` → 200 `audio/mpeg`,
байти = `silence.mp3`; мова `kk-KZ` → `data-voice="no"`, `/speak` → 409.

`run_smoke` runs the script in-process (runpy, as `__main__`) from the repository root, with
`subprocess.Popen` watched: the launch of `thinkhow.web.app:app` is recorded (command, environment) and a
folder of the test is put first on the server's `PYTHONPATH`. Its `sitecustomize.py` always leaves a mark
(the server really ran it) and, for a «fails when» test, wraps the app in a middleware that changes one
answer of the server — so the smoke's own checks are judged by what it does when the server misbehaves.
Rules pick answers by method, status and body, never by the order of the smoke's steps.
"""

from __future__ import annotations

import io
import os
import runpy
import subprocess
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "scripts" / "smoke_test_voice_synthesis.py"
APP = "thinkhow.web.app:app"

MARK = """
import os as _os
with open(_os.environ["VS_SMOKE_MARK"], "a", encoding="utf-8") as _f:
    _f.write(str(_os.getpid()) + "\\n")
"""

# A rule: {"method", "path" (None = any), "status" (the original), "has" (bytes the body must hold, or None),
# "new_status" (or None), "replace" (bytes replaced by as many X, or None), "garble" (flip every body byte),
# "content_type" (a new Content-Type, or None)}. The body keeps its length, so Content-Length stays true.
REWRITE = """
import thinkhow.web.server as _srv
import thinkhow.web as _web

_RULES = {rules!r}
_orig_create_app = _srv.create_app


class _Rewrite:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        held = []

        async def keep(message):
            held.append(message)

        await self.app(scope, receive, keep)
        start = next(m for m in held if m["type"] == "http.response.start")
        body = b"".join(m.get("body", b"") for m in held if m["type"] == "http.response.body")
        status = start["status"]
        headers = list(start.get("headers", []))
        for rule in _RULES:
            if scope.get("method") != rule["method"]:
                continue
            if rule["path"] is not None and scope.get("path") != rule["path"]:
                continue
            if status != rule["status"]:
                continue
            if rule["has"] is not None and rule["has"] not in body:
                continue
            if rule["new_status"] is not None:
                status = rule["new_status"]
            if rule["replace"] is not None:
                body = body.replace(rule["replace"], b"X" * len(rule["replace"]))
            if rule["garble"]:
                body = bytes(b ^ 0xFF for b in body)
            if rule["content_type"] is not None:
                headers = [(k, v) for k, v in headers if k.lower() != b"content-type"]
                headers.append((b"content-type", rule["content_type"].encode()))
            break
        await send({{**start, "status": status, "headers": headers}})
        await send({{"type": "http.response.body", "body": body, "more_body": False}})


def create_app(deps):
    app = _orig_create_app(deps)
    app.add_middleware(_Rewrite)
    return app


_srv.create_app = create_app
if hasattr(_web, "create_app"):
    _web.create_app = create_app
"""


def rule(
    method: str,
    status: int,
    *,
    path: str | None = None,
    has: bytes | None = None,
    new_status: int | None = None,
    replace: bytes | None = None,
    garble: bool = False,
    content_type: str | None = None,
) -> dict[str, Any]:
    return {
        "method": method,
        "path": path,
        "status": status,
        "has": has,
        "new_status": new_status,
        "replace": replace,
        "garble": garble,
        "content_type": content_type,
    }


def rewrite(*rules: dict[str, Any]) -> str:
    return REWRITE.format(rules=list(rules))


@dataclass
class Launch:
    cmd: list[str]
    environ: dict[str, str]
    proc: subprocess.Popen[Any] | None = None


@dataclass
class Run:
    ok: bool
    out: str
    launches: list[Launch] = field(default_factory=list)
    marked: bool = False


def run_smoke(monkeypatch: pytest.MonkeyPatch, tmp: Path, sabotage: str = "") -> Run:
    sab = tmp / "sabotage"
    sab.mkdir()
    (sab / "sitecustomize.py").write_text(MARK + sabotage, encoding="utf-8")
    mark = tmp / "mark.txt"
    launches: list[Launch] = []
    real_popen = subprocess.Popen

    def spy(args: Any, *rest: Any, **kwargs: Any) -> subprocess.Popen[Any]:
        cmd = args.split() if isinstance(args, str) else [os.fsdecode(a) for a in args]
        launch: Launch | None = None
        if any(APP in part for part in cmd):
            given = kwargs.get("env")
            environ = {str(k): str(v) for k, v in (given if given is not None else os.environ).items()}
            launch = Launch(cmd=cmd, environ=dict(environ))
            environ["PYTHONPATH"] = os.pathsep.join(p for p in (str(sab), environ.get("PYTHONPATH", "")) if p)
            environ["VS_SMOKE_MARK"] = str(mark)
            kwargs["env"] = environ
        proc = real_popen(args, *rest, **kwargs)
        if launch is not None:
            launch.proc = proc
            launches.append(launch)
        return proc

    out = io.StringIO()
    ok = True
    try:
        with monkeypatch.context() as m:
            m.setattr(subprocess, "Popen", spy)
            m.chdir(REPO)
            try:
                with redirect_stdout(out), redirect_stderr(out):
                    runpy.run_path(str(SCRIPT), run_name="__main__")
            except SystemExit as stop:
                ok = stop.code in (0, None)
            except Exception as error:  # an assertion or any error of the smoke is its failure
                out.write(f"\n{type(error).__name__}: {error}")
                ok = False
    finally:
        for launch in launches:
            assert launch.proc is not None
            try:
                launch.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                launch.proc.kill()
                launch.proc.wait(timeout=10)
    return Run(ok=ok, out=out.getvalue(), launches=launches, marked=mark.exists())


def server_ran(run: Run) -> None:
    assert run.launches, "the smoke launched no process running thinkhow.web.app:app"
    assert run.marked, "the server process did not run with the PYTHONPATH the smoke gave it"
