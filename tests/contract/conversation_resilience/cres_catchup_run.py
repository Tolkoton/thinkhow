"""Helper for the conversation-resilience catch-up tests of the smoke script (slice tester), from the
contract.

The contract («Exit criterion»):
Smoke: `uv run --with playwright==1.64.1 python scripts/smoke_test_conversation_resilience.py` — стенд
`scripts/talk_harness.py`, локальний режим; друге речення першої відповіді — `/speak` 502 через Playwright
`route`; після одного `click`: 3 цикли (третій доходить до `listening` після пропущеного речення
першого), речень на `/speak` 200 менше, ніж запитів, на одне; `navigator.wakeLock.request` —
викликано з `"screen"`; осцилятор ~880 Гц (сигнал `listening`) запущено щонайменше 3 рази. Вивід — у
`.engine/artifacts/conversation-resilience/smoke.txt` (пише сам скрипт). Порогів немає.

`run_smoke` runs exactly that command from the repository root, with a folder of the test first on
`PYTHONPATH`. Its `sitecustomize.py`:

- in every Python process that loads it, wraps `subprocess.Popen`: a child gets the same folder first on its
  `PYTHONPATH`; a child running `thinkhow.web.app` (the server, however the script launches it) is recorded
  (command, `THINKHOW_LOCAL`) and marked as the server;
- in the server, wraps the app in a middleware that records every `/voice`, `/reply`, `/retry`, `/speak`
  request that reaches the server and can change answers by rules (a kind, the n-th or from the n-th), and
  answers the test's own beacons (`/__crcu/<what>`), which the page sends when the test's script saw
  something;
- in the server, serves `/static/conversation.js` as the real file with the test's script put BEFORE it:
  always a watcher (clicks on `#talk`, every `data-state` of `#talk`, every `/speak` fetch and its status as
  the page sees it — after any Playwright `route` —, calls of `navigator.wakeLock.request`), and for a
  «fails when» test one breakage of the page.

The script writes into `.engine/artifacts/conversation-resilience/`; whatever it changes there is put back.
"""

from __future__ import annotations

import functools
import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[3]
SCRIPT = "scripts/smoke_test_conversation_resilience.py"
APP = "thinkhow.web.app"
JS = REPO / "src" / "thinkhow" / "web" / "static" / "conversation.js"
ARTIFACTS = REPO / ".engine" / "artifacts" / "conversation-resilience"

SITECUSTOMIZE = r"""
import json as _json
import os as _os

_HERE = _os.path.dirname(_os.path.abspath(__file__))


def _log(record):
    path = _os.environ.get("CRCU_LOG", "")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(_json.dumps(record) + "\n")


try:
    import subprocess as _sp

    _orig_init = _sp.Popen.__init__

    def _init(self, args, *rest, **kwargs):
        env = kwargs.get("env")
        env = dict(_os.environ if env is None else env)
        parts = [p for p in env.get("PYTHONPATH", "").split(_os.pathsep) if p]
        if _HERE not in parts:
            env["PYTHONPATH"] = _os.pathsep.join([_HERE, *parts])
        for key in ("CRCU_LOG", "CRCU_RULES", "CRCU_JS"):
            env.setdefault(key, _os.environ.get(key, ""))
        cmd = args.split() if isinstance(args, str) else [_os.fsdecode(a) for a in args]
        if any("thinkhow.web.app" in part for part in cmd):
            env["CRCU_SERVER"] = "1"
            _log({"kind": "launch", "cmd": cmd, "local": env.get("THINKHOW_LOCAL", "")})
        kwargs["env"] = env
        _orig_init(self, args, *rest, **kwargs)

    _sp.Popen.__init__ = _init
except Exception:
    pass


if _os.environ.get("CRCU_SERVER") == "1":
    import urllib.parse as _up

    _RULES = _json.loads(_os.environ.get("CRCU_RULES") or "[]")
    _COUNT = {}

    def _segment(path):
        return path.rstrip("/").rsplit("/", 1)[-1]

    class _Watch:
        def __init__(self, app):
            self.app = app

        async def __call__(self, scope, receive, send):
            if scope.get("type") != "http":
                await self.app(scope, receive, send)
                return
            path = scope.get("path", "")
            if path.startswith("/__crcu/"):
                while True:
                    message = await receive()
                    if not message.get("more_body"):
                        break
                _log({"kind": "beacon", "what": path[len("/__crcu/"):]})
                await send({"type": "http.response.start", "status": 204, "headers": []})
                await send({"type": "http.response.body", "body": b""})
                return
            seg = _segment(path)
            if scope.get("method") != "POST" or seg not in ("voice", "reply", "retry", "speak"):
                await self.app(scope, receive, send)
                return
            _COUNT[seg] = _COUNT.get(seg, 0) + 1
            n = _COUNT[seg]
            headers_in = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
            chunks = []

            async def keep_receive():
                message = await receive()
                if message.get("type") == "http.request":
                    chunks.append(message.get("body", b""))
                return message

            logged = []

            def log_request(status):
                if logged:
                    return
                logged.append(1)
                body = b"".join(chunks)
                record = {"kind": "req", "seg": seg, "n": n, "status": status, "size": len(body),
                          "ctype": headers_in.get("content-type", "")}
                if seg == "reply":
                    record["spoken"] = _up.parse_qs(body.decode("utf-8", "replace")).get("spoken", [])
                _log(record)

            rule = next((r for r in _RULES if r["seg"] == seg and r["nth"] in (None, n)
                         and n >= (r.get("from") or 0)), None)
            if rule is None:
                async def pass_send(message):
                    if message["type"] == "http.response.start":
                        log_request(message["status"])
                    await send(message)

                await self.app(scope, keep_receive, pass_send)
                return
            held = []

            async def hold(message):
                held.append(message)

            await self.app(scope, keep_receive, hold)
            start = next(m for m in held if m["type"] == "http.response.start")
            body = b"".join(m.get("body", b"") for m in held if m["type"] == "http.response.body")
            status = start["status"]
            headers = list(start.get("headers", []))
            log_request(status)
            if rule.get("garble"):
                body = bytes(b ^ 0xFF for b in body)
            if rule.get("status") is not None:
                status = rule["status"]
            if rule.get("html") is not None:
                body = rule["html"].encode("utf-8")
                drop = (b"content-type", b"content-length")
                headers = [(k, v) for k, v in headers if k.lower() not in drop]
                headers.append((b"content-type", b"text/html; charset=utf-8"))
                headers.append((b"content-length", str(len(body)).encode()))
            _log({"kind": "rewritten", "seg": seg, "n": n})
            await send({**start, "status": status, "headers": headers})
            await send({"type": "http.response.body", "body": body, "more_body": False})

    try:
        import thinkhow.web.server as _srv

        _orig_create_app = _srv.create_app

        def create_app(deps):
            app = _orig_create_app(deps)
            app.add_middleware(_Watch)
            return app

        _srv.create_app = create_app
    except Exception as _error:
        _log({"kind": "hook-error", "error": repr(_error)})

    try:
        import starlette.staticfiles as _sf

        _orig_lookup = _sf.StaticFiles.lookup_path

        def _lookup(self, path):
            js = _os.environ.get("CRCU_JS", "")
            if js and path.replace("\\", "/").rstrip("/").endswith("conversation.js"):
                _log({"kind": "js-served"})
                return js, _os.stat(js)
            return _orig_lookup(self, path)

        _sf.StaticFiles.lookup_path = _lookup
    except Exception as _error:
        _log({"kind": "hook-error", "error": repr(_error)})
"""

# Put before the real conversation.js in every run.
WATCH_JS = r"""
(function () {
  window.__crcuBeacon = function (what) {
    try { navigator.sendBeacon("/__crcu/" + what, ""); } catch (e) { /* the beacon is the test's only */ }
  };
  document.addEventListener("click", function (event) {
    var target = event.target;
    if (target && target.closest && target.closest("#talk")) {
      window.__crcuBeacon(event.isTrusted ? "click" : "click-untrusted");
    }
  }, true);
  var speakN = 0;
  var realFetch = window.fetch;
  window.fetch = function (input, init) {
    var url = typeof input === "string" ? input : (input && input.url) || String(input);
    var path = url.split("?")[0].replace(/\/+$/, "");
    if (!/\/speak$/.test(path)) {
      return realFetch.apply(this, arguments);
    }
    speakN += 1;
    var n = speakN;
    return realFetch.apply(this, arguments).then(function (response) {
      window.__crcuBeacon("speak-" + n + "-" + response.status);
      return response;
    }, function (error) {
      window.__crcuBeacon("speak-" + n + "-network");
      throw error;
    });
  };
  try {
    var lock = navigator.wakeLock;
    if (lock && typeof lock.request === "function") {
      var realRequest = lock.request;
      lock.request = function (type) {
        window.__crcuBeacon("wakelock-" + String(type));
        return realRequest.apply(this, arguments);
      };
    }
  } catch (e) { /* no wake lock: nothing to watch */ }
  var talk = document.getElementById("talk");
  if (talk) {
    var last = null;
    var seen = function () {
      var state = talk.getAttribute("data-state");
      if (state !== last) {
        last = state;
        window.__crcuBeacon("state-" + String(state));
      }
    };
    new MutationObserver(seen).observe(talk, { attributes: true, attributeFilter: ["data-state"] });
  }
})();
"""

# The page has no Screen Wake Lock API: `navigator.wakeLock` is undefined (the contract: «немає чи
# відмова — мовчки, режим працює»), so the page never calls `navigator.wakeLock.request`.
NO_WAKE_LOCK_JS = r"""
(function () {
  try { delete navigator.wakeLock; } catch (e) { /* not an own property */ }
  var hide = { get: function () { return undefined; }, configurable: true };
  try { Object.defineProperty(navigator, "wakeLock", hide); } catch (e) { /* tried */ }
  try { Object.defineProperty(Navigator.prototype, "wakeLock", hide); } catch (e) { /* tried */ }
  window.__crcuBeacon(navigator.wakeLock === undefined ? "wakelock-gone" : "wakelock-still-there");
})();
"""

# Every oscillator of the page sounds at 200 Hz, whatever frequency the page gives it (a value, an
# automation, the constructor's options): no tone of the page is ~880 Hz.
OSC_200_JS = r"""
(function () {
  var HZ = 200;
  function pin(node) {
    var param = node && node.frequency;
    if (!param || param.__crcuPinned) { return node; }
    var desc = Object.getOwnPropertyDescriptor(param, "value") ||
      Object.getOwnPropertyDescriptor(AudioParam.prototype, "value");
    Object.defineProperty(param, "value", {
      configurable: true,
      get: function () { return desc.get.call(param); },
      set: function () { desc.set.call(param, HZ); }
    });
    ["setValueAtTime", "linearRampToValueAtTime", "exponentialRampToValueAtTime", "setTargetAtTime"]
      .forEach(function (name) {
        var real = param[name];
        if (typeof real !== "function") { return; }
        param[name] = function () {
          var args = Array.prototype.slice.call(arguments);
          args[0] = HZ;
          return real.apply(param, args);
        };
      });
    if (typeof param.setValueCurveAtTime === "function") {
      var realCurve = param.setValueCurveAtTime;
      param.setValueCurveAtTime = function (values, start, duration) {
        var flat = new Float32Array(values.length).fill(HZ);
        return realCurve.call(param, flat, start, duration);
      };
    }
    try { desc.set.call(param, HZ); } catch (e) { /* tried */ }
    param.__crcuPinned = true;
    window.__crcuBeacon("osc-pinned");
    return node;
  }
  function wrapCreate(holder) {
    if (!holder || !Object.prototype.hasOwnProperty.call(holder, "createOscillator")) { return; }
    var realCreate = holder.createOscillator;
    if (typeof realCreate !== "function" || realCreate.__crcuPinned) { return; }
    var wrapped = function () { return pin(realCreate.apply(this, arguments)); };
    wrapped.__crcuPinned = true;
    holder.createOscillator = wrapped;
  }
  // wherever createOscillator lives: the standard prototype, a prototype or an instance someone patched
  [window.BaseAudioContext, window.AudioContext, window.webkitAudioContext].forEach(function (C) {
    if (C) { wrapCreate(C.prototype); }
  });
  ["AudioContext", "webkitAudioContext"].forEach(function (name) {
    var RealCtx = window[name];
    if (!RealCtx) { return; }
    var Ctx = function () {
      var ctx = Reflect.construct(RealCtx, arguments, new.target || Ctx);
      wrapCreate(ctx);
      return ctx;
    };
    Ctx.prototype = RealCtx.prototype;
    Object.setPrototypeOf(Ctx, RealCtx);
    window[name] = Ctx;
  });
  var RealOsc = window.OscillatorNode;
  if (RealOsc) {
    var Pinned = function (ctx, options) {
      var opts = Object.assign({}, options || {});
      if ("frequency" in opts) { opts.frequency = HZ; }
      return pin(new RealOsc(ctx, opts));
    };
    Pinned.prototype = RealOsc.prototype;
    window.OscillatorNode = Pinned;
  }
})();
"""


def rule(
    seg: str,
    nth: int | None = None,
    *,
    start: int | None = None,
    status: int | None = None,
    html: str | None = None,
    garble: bool = False,
) -> dict[str, Any]:
    """Change the answer of `seg`: the `nth` request, or every one from the `start`-th (None: every one)."""
    return {"seg": seg, "nth": nth, "from": start, "status": status, "html": html, "garble": garble}


@dataclass
class Run:
    code: int
    out: str
    records: list[dict[str, Any]] = field(default_factory=list)
    smoke_txt: str | None = None

    def kind(self, kind: str) -> list[dict[str, Any]]:
        return [r for r in self.records if r.get("kind") == kind]

    def requests(self, seg: str) -> list[dict[str, Any]]:
        return [r for r in self.kind("req") if r.get("seg") == seg]

    def beacons(self, what: str) -> int:
        return len([r for r in self.kind("beacon") if r.get("what") == what])

    def beacons_starting(self, prefix: str) -> list[str]:
        return [str(r["what"]) for r in self.kind("beacon") if str(r.get("what", "")).startswith(prefix)]

    def page_speak(self) -> dict[int, str]:
        """The page's /speak fetches, in the order the page made them: n → the status it saw."""
        seen: dict[int, str] = {}
        for what in self.beacons_starting("speak-"):
            _, n, status = what.split("-", 2)
            seen[int(n)] = status
        return dict(sorted(seen.items()))


def _snapshot(folder: Path) -> dict[Path, bytes]:
    if not folder.is_dir():
        return {}
    return {p: p.read_bytes() for p in folder.rglob("*") if p.is_file()}


def _restore(folder: Path, before: dict[Path, bytes], existed: bool) -> None:
    if not existed:
        shutil.rmtree(folder, ignore_errors=True)
        return
    for p in [p for p in folder.rglob("*") if p.is_file()]:
        if p not in before:
            p.unlink()
    for p, data in before.items():
        if not p.is_file() or p.read_bytes() != data:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)


def run_smoke(tmp: Path, *, rules: list[dict[str, Any]] | None = None, breakage: str = "") -> Run:
    hook = tmp / "hook"
    hook.mkdir()
    (hook / "sitecustomize.py").write_text(SITECUSTOMIZE, encoding="utf-8")
    js = tmp / "conversation.js"
    js.write_text(WATCH_JS + breakage + "\n" + JS.read_text(encoding="utf-8"), encoding="utf-8")
    log = tmp / "log.jsonl"
    log.write_text("", encoding="utf-8")
    uv = shutil.which("uv")
    assert uv, "uv is not on PATH"
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(hook), *[p for p in env.get("PYTHONPATH", "").split(os.pathsep) if p]]
    )
    env["CRCU_LOG"] = str(log)
    env["CRCU_RULES"] = json.dumps(rules or [])
    env["CRCU_JS"] = str(js)
    existed = ARTIFACTS.is_dir()
    before = _snapshot(ARTIFACTS)
    # put back by _restore; whatever smoke.txt is there after the run, this run wrote
    (ARTIFACTS / "smoke.txt").unlink(missing_ok=True)
    try:
        proc = subprocess.run(
            [uv, "run", "--with", "playwright==1.64.1", "python", SCRIPT],
            cwd=REPO,
            env=env,
            capture_output=True,
            text=True,
            timeout=480,
        )
        smoke = ARTIFACTS / "smoke.txt"
        written = smoke.read_text(encoding="utf-8", errors="replace") if smoke.is_file() else None
    finally:
        _restore(ARTIFACTS, before, existed)
    records = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]
    out = proc.stdout[-6000:] + "\n--- stderr ---\n" + proc.stderr[-6000:]
    return Run(proc.returncode, out, records, written)


@functools.lru_cache(maxsize=1)
def clean_run() -> Run:
    """The run with nothing broken (only the watcher), shared by every test that reads it."""
    with tempfile.TemporaryDirectory(prefix="crcu-") as tmp:
        return run_smoke(Path(tmp))


def server_ran(run: Run) -> None:
    assert run.kind("launch"), "the smoke launched no process running thinkhow.web.app\n" + run.out
    assert not run.kind("hook-error"), f"the test's hook failed in the server: {run.kind('hook-error')}"
    assert run.kind("js-served"), "the test's conversation.js never reached the browser\n" + run.out
