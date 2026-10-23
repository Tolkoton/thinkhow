"""Helper for the voice-language catch-up tests of the smoke script (slice tester), from the contract.

`run_smoke` runs `scripts/smoke_test_voice_language.py` in-process (runpy, as `__main__`) from the repository
root, with `subprocess.Popen` watched: the launch of `uvicorn thinkhow.web.app:app` is recorded (command,
environment, working folder) and a folder of the test is put first on the server's `PYTHONPATH`. Its
`sitecustomize.py` always leaves a mark (the server really ran it) and, for a «fails when» test, breaks one
fact inside the server. The smoke's records `.engine/artifacts/spikes/voice-language-smoke-*.txt` written
during a run are captured in `Run.written` and then restored, so the builder's record is left as it was.
"""

from __future__ import annotations

import io
import os
import runpy
import subprocess
from contextlib import redirect_stdout
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "scripts" / "smoke_test_voice_language.py"
SPIKES = REPO / ".engine" / "artifacts" / "spikes"
APP = "thinkhow.web.app:app"
SKIP_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "node_modules",
    ".claude",
}

MARK = """
import os as _os
with open(_os.environ["VL_SMOKE_MARK"], "a", encoding="utf-8") as _f:
    _f.write(str(_os.getpid()) + "\\n")
"""

# Rules on the server's answers: (method, path, the original status, nth such answer or 0 for every one,
# the new status or None, bytes of the body replaced by as many X, a new Location or None).
REWRITE = """
import thinkhow.web.server as _srv
import thinkhow.web as _web

_RULES = {rules!r}
_SEEN = {{}}
_orig_create_app = _srv.create_app


class _Rewrite:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        state = {{"rule": None}}

        async def changed(message):
            if message["type"] == "http.response.start":
                for i, rule in enumerate(_RULES):
                    method, path, status, nth, new_status, _old, location = rule
                    hit = scope.get("method") == method and scope.get("path") == path
                    if hit and message["status"] == status:
                        _SEEN[i] = _SEEN.get(i, 0) + 1
                        if nth in (0, _SEEN[i]):
                            state["rule"] = rule
                            if new_status is not None:
                                message = {{**message, "status": new_status}}
                            if location is not None:
                                headers = [
                                    (k, location.encode() if k.lower() == b"location" else v)
                                    for k, v in message.get("headers", [])
                                ]
                                message = {{**message, "headers": headers}}
                            break
            elif message["type"] == "http.response.body" and state["rule"] is not None and state["rule"][5]:
                old = state["rule"][5]
                message = {{**message, "body": message.get("body", b"").replace(old, b"X" * len(old))}}
            await send(message)

        await self.app(scope, receive, changed)


def create_app(deps):
    app = _orig_create_app(deps)
    app.add_middleware(_Rewrite)
    return app


_srv.create_app = create_app
if hasattr(_web, "create_app"):
    _web.create_app = create_app
"""

# workspace.set_language replaced before the app is imported; {body} sees `storage, user, code` and `_orig`.
PATCH_SET_LANGUAGE = """
import dataclasses as _dc
import sys as _sys
import thinkhow.workspace as _ws

_orig = _ws.set_language


def set_language(storage, user, code):
{body}


_ws.set_language = set_language
_defining = _sys.modules[_orig.__module__]
if hasattr(_defining, "set_language"):
    _defining.set_language = set_language
"""

# The profile gets another email than the person's.
OTHER_EMAIL = PATCH_SET_LANGUAGE.format(
    body='    return _orig(storage, _dc.replace(user, email="someone-else@localhost"), code)'
)

# A refused `ru-RU` still changes the profile (to `uk-UA`) before the refusal.
RU_WRITES_FIRST = PATCH_SET_LANGUAGE.format(
    body=(
        '    if code == "ru-RU":\n'
        '        _orig(storage, user, "uk-UA")\n'
        "        raise ValueError(code)\n"
        "    return _orig(storage, user, code)"
    )
)

Rule = tuple[str, str, int, int, int | None, bytes, str | None]


def rewrite(*rules: Rule) -> str:
    return REWRITE.format(rules=list(rules))


@dataclass
class Launch:
    cmd: list[str]
    environ: dict[str, str]
    cwd: Path
    proc: subprocess.Popen[Any] | None = None


@dataclass
class Run:
    ok: bool
    out: str
    launches: list[Launch] = field(default_factory=list)
    marked: bool = False
    written: dict[str, bytes] = field(default_factory=dict)  # smoke records written during the run


def _records() -> dict[Path, tuple[bytes, int]]:
    return {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in SPIKES.glob("voice-language-smoke-*.txt")}


def run_smoke(monkeypatch: pytest.MonkeyPatch, tmp: Path, sabotage: str = "") -> Run:
    sab = tmp / "sabotage"
    sab.mkdir()
    (sab / "sitecustomize.py").write_text(MARK + sabotage, encoding="utf-8")
    mark = tmp / "mark.txt"
    temp = tmp / "temp"
    temp.mkdir()
    launches: list[Launch] = []
    real_popen = subprocess.Popen

    def spy(args: Any, *rest: Any, **kwargs: Any) -> subprocess.Popen[Any]:
        cmd = args.split() if isinstance(args, str) else [os.fsdecode(a) for a in args]
        launch: Launch | None = None
        if any(APP in part for part in cmd):
            given = kwargs.get("env")
            environ = {str(k): str(v) for k, v in (given if given is not None else os.environ).items()}
            launch = Launch(cmd=cmd, environ=dict(environ), cwd=Path(kwargs.get("cwd") or os.getcwd()))
            environ["PYTHONPATH"] = os.pathsep.join(p for p in (str(sab), environ.get("PYTHONPATH", "")) if p)
            environ["VL_SMOKE_MARK"] = str(mark)
            kwargs["env"] = environ
        proc = real_popen(args, *rest, **kwargs)
        if launch is not None:
            launch.proc = proc
            launches.append(launch)
        return proc

    before = _records()
    out = io.StringIO()
    written: dict[str, bytes] = {}
    ok = True
    try:
        with monkeypatch.context() as m:
            m.setattr(subprocess, "Popen", spy)
            for name in ("TMPDIR", "TEMP", "TMP"):
                m.setenv(name, str(temp))
            m.setattr("tempfile.tempdir", None)
            m.chdir(REPO)
            try:
                with redirect_stdout(out):
                    runpy.run_path(str(SCRIPT), run_name="__main__")
            except SystemExit as stop:
                ok = stop.code in (0, None)
            except Exception:
                ok = False
    finally:
        for launch in launches:
            assert launch.proc is not None
            try:
                launch.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                launch.proc.kill()
                launch.proc.wait(timeout=10)
        after = _records()
        for path, state in after.items():
            if before.get(path) != state:
                written[path.name] = state[0]
        for path in after:
            if path not in before:
                path.unlink()
        for path, (data, mtime) in before.items():
            path.write_bytes(data)
            os.utime(path, ns=(mtime, mtime))
    return Run(ok=ok, out=out.getvalue(), launches=launches, marked=mark.exists(), written=written)


def server_ran(run: Run) -> None:
    assert run.launches, "the smoke launched no process running thinkhow.web.app:app"
    assert run.marked, "the server process did not run with the PYTHONPATH the smoke gave it"


def repo_files() -> set[Path]:
    found: set[Path] = set()
    for root, dirs, files in os.walk(REPO):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        found.update(Path(root) / f for f in files)
    return found
