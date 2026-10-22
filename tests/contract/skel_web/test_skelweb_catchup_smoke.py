"""Catch-up contract tests of skel-web: the smoke script (slice tester).

Written from the contract (.engine/slices/skel-web.md, «Exit criterion» and «Hardest seams», Seam 4), not
from the code. The script runs in-process (runpy, as `__main__`) from the repository root, with
`subprocess.Popen` watched: the launch of `uvicorn thinkhow.web.app:app` is recorded (command, environment,
working folder, port) and a folder of this test is put first on the server's `PYTHONPATH`. Its
`sitecustomize.py` always leaves a mark (the server process really ran it) and, for a «fails when» test,
breaks one fact inside the server, so the smoke's own checks are judged by what it does when the server
misbehaves.
"""

from __future__ import annotations

import contextlib
import io
import os
import runpy
import socket
import subprocess
import time
from collections.abc import Iterator
from contextlib import redirect_stdout
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "scripts" / "smoke_test_skel_web.py"
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
with open(_os.environ["SKELWEB_SMOKE_MARK"], "a", encoding="utf-8") as _f:
    _f.write(str(_os.getpid()) + "\\n")
"""

# The home page of the server answers with another status, or with a phrase replaced by as many bytes.
REWRITE_HOME = """
import thinkhow.web.server as _srv
import thinkhow.web as _web

_STATUS = {status!r}
_OLD = {old!r}
_NEW = b"X" * len(_OLD)
_orig_create_app = _srv.create_app


class _RewriteHome:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http" or scope.get("method") != "GET" or scope.get("path") != "/":
            await self.app(scope, receive, send)
            return

        async def changed(message):
            if message["type"] == "http.response.start" and _STATUS is not None:
                message = {{**message, "status": _STATUS}}
            if message["type"] == "http.response.body" and _OLD:
                message = {{**message, "body": message.get("body", b"").replace(_OLD, _NEW)}}
            await send(message)

        await self.app(scope, receive, changed)


def create_app(deps):
    app = _orig_create_app(deps)
    app.add_middleware(_RewriteHome)
    return app


_srv.create_app = create_app
if hasattr(_web, "create_app"):
    _web.create_app = create_app
"""

# workspace.reply streams every event but `Answered`: the SSE stream ends after the deltas.
DROP_ANSWERED = """
import sys as _sys
import thinkhow.workspace as _ws

_orig_reply = _ws.reply


def reply(*args, **kwargs):
    events = _orig_reply(*args, **kwargs)

    def gen():
        for event in events:
            if type(event).__name__ == "Answered":
                continue
            yield event

    return gen()


_ws.reply = reply
_defining = _sys.modules[_orig_reply.__module__]
if hasattr(_defining, "reply"):
    _defining.reply = reply
"""

# The server process starts 3 seconds late.
SLOW_START = """
import time as _time
_time.sleep(3)
"""


@dataclass
class Launch:
    cmd: list[str]
    env: dict[str, str]
    cwd: Path
    port: int | None
    port_was_free: bool
    proc: subprocess.Popen[Any] | None = None
    stopped: bool = False


@dataclass
class Run:
    ok: bool
    out: str
    launches: list[Launch] = field(default_factory=list)
    marked: bool = False


def _port_of(cmd: list[str], env: dict[str, str]) -> int | None:
    for i, arg in enumerate(cmd):
        if arg == "--port" and i + 1 < len(cmd):
            return int(cmd[i + 1])
        if arg.startswith("--port="):
            return int(arg.split("=", 1)[1])
    if env.get("UVICORN_PORT"):
        return int(env["UVICORN_PORT"])
    return 8000  # uvicorn's own default


def _free(port: int | None) -> bool:
    if port is None:
        return False
    with socket.socket() as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


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
            env = {str(k): str(v) for k, v in (given if given is not None else os.environ).items()}
            cwd = Path(kwargs.get("cwd") or os.getcwd())
            port = _port_of(cmd, env)
            launch = Launch(cmd=cmd, env=dict(env), cwd=cwd, port=port, port_was_free=_free(port))
            env["PYTHONPATH"] = os.pathsep.join(p for p in (str(sab), env.get("PYTHONPATH", "")) if p)
            env["SKELWEB_SMOKE_MARK"] = str(mark)
            kwargs["env"] = env
        proc = real_popen(args, *rest, **kwargs)
        if launch is not None:
            launch.proc = proc
            launches.append(launch)
        return proc

    out = io.StringIO()
    with monkeypatch.context() as m:
        m.setattr(subprocess, "Popen", spy)
        for name in ("TMPDIR", "TEMP", "TMP"):
            m.setenv(name, str(temp))
        m.setattr("tempfile.tempdir", None)
        m.chdir(REPO)
        ok = True
        try:
            with redirect_stdout(out):
                runpy.run_path(str(SCRIPT), run_name="__main__")
        except SystemExit as stop:
            ok = stop.code in (0, None)
        except Exception:
            ok = False
    for launch in launches:
        assert launch.proc is not None
        try:
            launch.proc.wait(timeout=5)
            launch.stopped = True
        except subprocess.TimeoutExpired:
            launch.proc.kill()
            launch.proc.wait(timeout=10)
    return Run(ok=ok, out=out.getvalue(), launches=launches, marked=mark.exists())


def server_ran(run: Run) -> None:
    assert run.launches, "the smoke launched no process running thinkhow.web.app:app"
    assert run.marked, "the server process did not run with the PYTHONPATH the smoke gave it"


def repo_files() -> set[Path]:
    found: set[Path] = set()
    for root, dirs, files in os.walk(REPO):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        found.update(Path(root) / f for f in files)
    return found


@contextlib.contextmanager
def occupied(*ports: int) -> Iterator[None]:
    held: list[socket.socket] = []
    try:
        for port in ports:
            s = socket.socket()
            try:
                s.bind(("127.0.0.1", port))
                s.listen()
                held.append(s)
            except OSError:
                s.close()  # someone else holds it already: it is occupied either way
        yield
    finally:
        for s in held:
            s.close()


# --- the whole run ------------------------------------------------------------------------------------


def test_smoke_passes_through_home_topic_reply_and_answered(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    run = run_smoke(monkeypatch, tmp_path)
    assert run.ok, run.out
    server_ran(run)


def test_smoke_launches_uvicorn_with_the_app_in_local_mode_as_the_owner(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    run = run_smoke(monkeypatch, tmp_path)
    assert run.ok, run.out
    server_ran(run)
    launch = run.launches[0]
    assert any(part == "uvicorn" or part.endswith("/uvicorn") for part in launch.cmd), launch.cmd
    assert APP in launch.cmd, launch.cmd
    entries = [p for p in launch.env.get("PYTHONPATH", "").split(os.pathsep) if p]
    assert (REPO / "src").resolve() in {(launch.cwd / p).resolve() for p in entries}, entries
    assert launch.env.get("THINKHOW_LOCAL", "").strip().lower() == "true"
    assert launch.env.get("THINKHOW_OWNER_EMAIL") == "owner@localhost"


def test_smoke_works_in_a_temporary_folder_not_in_the_repository(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    before = repo_files()
    run = run_smoke(monkeypatch, tmp_path)
    assert run.ok, run.out
    server_ran(run)
    local_dir = Path(run.launches[0].env["THINKHOW_LOCAL_DIR"])
    if not local_dir.is_absolute():
        local_dir = run.launches[0].cwd / local_dir
    assert local_dir.resolve().is_relative_to((tmp_path / "temp").resolve()), local_dir
    assert repo_files() - before == set()


def test_smoke_runs_the_server_on_a_free_port(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    with occupied(8000, 8080):
        run = run_smoke(monkeypatch, tmp_path)
    assert run.ok, run.out
    server_ran(run)
    launch = run.launches[0]
    assert launch.port not in (8000, 8080), launch.port
    assert launch.port_was_free, f"port {launch.port} was taken when the server was launched"


def test_smoke_waits_for_the_server_to_start(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    started = time.monotonic()
    run = run_smoke(monkeypatch, tmp_path, SLOW_START)
    assert run.ok, run.out
    server_ran(run)
    assert time.monotonic() - started >= 3


def test_smoke_stops_the_server(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    run = run_smoke(monkeypatch, tmp_path)
    assert run.ok, run.out
    server_ran(run)
    assert all(launch.stopped for launch in run.launches), "the server still ran 5 s after the smoke ended"


# --- the smoke's own checks: one broken fact at a time --------------------------------------------------


def test_smoke_fails_when_home_is_not_200(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    run = run_smoke(monkeypatch, tmp_path, REWRITE_HOME.format(status=500, old=b""))
    server_ran(run)
    assert not run.ok, "GET / → 500 was not caught"


def test_smoke_fails_when_home_has_no_my_topics(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    run = run_smoke(monkeypatch, tmp_path, REWRITE_HOME.format(status=None, old="Мої теми".encode()))
    server_ran(run)
    assert not run.ok, "a home page without «Мої теми» was not caught"


def test_smoke_fails_when_home_has_no_all_topics(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    run = run_smoke(monkeypatch, tmp_path, REWRITE_HOME.format(status=None, old="Усі теми".encode()))
    server_ran(run)
    assert not run.ok, "a home page without «Усі теми» was not caught"


def test_smoke_fails_when_the_stream_has_no_answered(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    run = run_smoke(monkeypatch, tmp_path, DROP_ANSWERED)
    server_ran(run)
    assert not run.ok, "an SSE stream that ended without `answered` was not caught"
