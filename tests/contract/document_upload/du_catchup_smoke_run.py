"""Helper for the document-upload catch-up tests of the smoke script (slice tester), from the contract.

The contract («Exit criterion»): `scripts/smoke_test_document_upload.py` prints `OK:` — real uvicorn in
local mode, real Chromium: screenshot of the topic page with `#attach` (no words, `aria-label` set);
`resume.pdf` → a `📎 resume.pdf` turn and a model answer; `resume.docx` → the same; reload → both turns still
there and `documents.json` holds both texts; `scan.pdf` → the message `err_document_unreadable` visible and
the turn count unchanged; a file over 32 MiB (a `set_input_files` buffer) → `js_document_too_large` visible
and no `/document` request sent; a `/document` answered 413 (`page.route`) with Cloud Run's own HTML → the
same words; a `/document` answered by the server's `DocumentTooLarge` → `err_document_too_large` visible.

`run_smoke` runs `uv run --project <repo> python scripts/smoke_test_document_upload.py` from a temporary
working folder (whatever the smoke writes relative to its folder lands there), with a folder of the test
first on `PYTHONPATH`. Its `sitecustomize.py`, in every Python process that loads it:

- wraps `subprocess.Popen`, so a child gets the same folder on its `PYTHONPATH` (and the test's variables);
- wraps `thinkhow.web.server.create_app`: every app gets a middleware that records each `/document` request
  (the multipart field names and file names, the size, the status, the user agent, whether uvicorn serves it)
  and, by the test's rules, changes ONE thing: a request refused before the app sees it, an answer of a given
  status given other words, or the text of an entry of `documents.json` after the app stored it; it puts the
  test's script first into the `<head>` of every HTML page and answers that script's beacons (`/__ducu/…`);
- wraps playwright's `Page.screenshot`, recording each call (and, with the sync API, whether `#attach` is on
  the page at that moment).

The page script always watches (files chosen on `input#document` with their real sizes, the page's `fetch` of
`/document` and the status it sees — after any `page.route`); for a «fails when» test it adds one breakage.
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
SCRIPT = REPO / "scripts" / "smoke_test_document_upload.py"
MIB_32 = 32 * 1024 * 1024
OTHER_WORDS = '<p class="error">DUCU: інші слова, не ті, що в контракті</p>'

SITECUSTOMIZE = r"""
import json as _json
import os as _os
import sys as _sys

_HERE = _os.path.dirname(_os.path.abspath(__file__))
_KEYS = ("DUCU_LOG", "DUCU_RULES", "DUCU_JS")


def _log(record):
    path = _os.environ.get("DUCU_LOG", "")
    if path:
        record = dict(record, pid=_os.getpid())
        with open(path, "a", encoding="utf-8") as f:
            f.write(_json.dumps(record) + "\n")


_RULES = _json.loads(_os.environ.get("DUCU_RULES") or "{}")

try:
    import subprocess as _sp

    _orig_init = _sp.Popen.__init__

    def _init(self, args, *rest, **kwargs):
        env = kwargs.get("env")
        env = dict(_os.environ if env is None else env)
        parts = [p for p in env.get("PYTHONPATH", "").split(_os.pathsep) if p]
        if _HERE not in parts:
            env["PYTHONPATH"] = _os.pathsep.join([_HERE, *parts])
        for key in _KEYS:
            env.setdefault(key, _os.environ.get(key, ""))
        cmd = args.split() if isinstance(args, str) else [_os.fsdecode(a) for a in args]
        _log({"kind": "launch", "cmd": cmd})
        kwargs["env"] = env
        _orig_init(self, args, *rest, **kwargs)

    _sp.Popen.__init__ = _init
except Exception as _error:
    _log({"kind": "hook-error", "error": repr(_error)})


def _by_uvicorn():
    frame = _sys._getframe(1)
    while frame is not None:
        if "uvicorn" in frame.f_code.co_filename.replace("\\", "/"):
            return True
        frame = frame.f_back
    return False


def _filenames(body):
    import re

    return [m.decode("utf-8", "replace") for m in re.findall(rb'filename="([^"]*)"', body)]


def _fields(body):
    import re

    return sorted({m.decode("utf-8", "replace") for m in re.findall(rb'form-data; name="([^"]*)"', body)})


def _replace_text(local_dir, name, text):
    from pathlib import Path

    done = 0
    for path in Path(local_dir).rglob("documents.json"):
        data = _json.loads(path.read_text(encoding="utf-8"))
        entries = data.get("entries", []) if isinstance(data, dict) else data
        for entry in entries:
            if isinstance(entry, dict) and entry.get("name") == name:
                entry["text"] = text
                done += 1
        path.write_text(_json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return done


def _watch(local_dir):
    class _Watch:
        def __init__(self, app):
            self.app = app

        async def __call__(self, scope, receive, send):
            if scope.get("type") != "http":
                await self.app(scope, receive, send)
                return
            path = scope.get("path", "")
            method = scope.get("method", "")
            headers_in = {
                k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])
            }
            if path.startswith("/__ducu/"):
                while True:
                    message = await receive()
                    if not message.get("more_body"):
                        break
                _log({"kind": "beacon", "what": path[len("/__ducu/"):]})
                await send({"type": "http.response.start", "status": 204, "headers": []})
                await send({"type": "http.response.body", "body": b""})
                return
            is_doc = method == "POST" and path.rstrip("/").endswith("/document")
            if is_doc:
                chunks = []
                while True:
                    message = await receive()
                    if message.get("type") != "http.request":
                        break
                    chunks.append(message.get("body", b""))
                    if not message.get("more_body"):
                        break
                body = b"".join(chunks)
                names = _filenames(body)
                record = {"kind": "doc", "files": names, "fields": _fields(body), "size": len(body),
                          "ua": headers_in.get("user-agent", ""), "uvicorn": _by_uvicorn()}
                deny = _RULES.get("deny")
                if deny and deny in names:
                    html = _RULES.get("html", "").encode("utf-8")
                    record.update(status=500, denied=True)
                    _log(record)
                    _log({"kind": "rewritten", "what": "deny " + deny})
                    await send({"type": "http.response.start", "status": 500,
                                "headers": [(b"content-type", b"text/html; charset=utf-8"),
                                            (b"content-length", str(len(html)).encode())]})
                    await send({"type": "http.response.body", "body": html, "more_body": False})
                    return
                sent = []

                async def replay():
                    if not sent:
                        sent.append(1)
                        return {"type": "http.request", "body": body, "more_body": False}
                    return await receive()

                inner_receive = replay
            elif method != "GET":
                await self.app(scope, receive, send)
                return
            else:
                inner_receive = receive
            held = []

            async def hold(message):
                held.append(message)

            await self.app(scope, inner_receive, hold)
            start = next(m for m in held if m["type"] == "http.response.start")
            out = b"".join(m.get("body", b"") for m in held if m["type"] == "http.response.body")
            status = start["status"]
            headers = list(start.get("headers", []))
            ctype = dict((k.lower(), v) for k, v in headers).get(b"content-type", b"").decode("latin-1")
            changed = False
            if is_doc:
                record.update(status=status, answered=b"event: answered" in out)
                _log(record)
                on = _RULES.get("on_status")
                if on is not None and status == on:
                    out = _RULES.get("html", "").encode("utf-8")
                    changed = True
                    _log({"kind": "rewritten", "what": "status %d" % status})
                text_for = _RULES.get("text_for")
                if text_for and text_for in names and status == 200:
                    n = _replace_text(local_dir, text_for, _RULES.get("text", ""))
                    _log({"kind": "rewritten" if n else "rewrite-missed", "what": "text of " + text_for})
            elif method == "GET" and status == 200 and ctype.startswith("text/html"):
                js = _os.environ.get("DUCU_JS", "")
                if js and b"<head" in out:
                    with open(js, "rb") as f:
                        tag = b"<script>" + f.read() + b"</script>"
                    at = out.index(b">", out.index(b"<head")) + 1
                    out = out[:at] + tag + out[at:]
                    changed = True
                    _log({"kind": "js-served", "path": path})
            if changed:
                drop = (b"content-length",)
                headers = [(k, v) for k, v in headers if k.lower() not in drop]
                headers.append((b"content-length", str(len(out)).encode()))
            await send({**start, "status": status, "headers": headers})
            await send({"type": "http.response.body", "body": out, "more_body": False})

    return _Watch


try:
    import thinkhow.web.server as _srv

    _orig_create_app = _srv.create_app

    def create_app(deps):
        app = _orig_create_app(deps)
        settings = deps.settings
        local_dir = _os.path.abspath(str(settings.local_dir))
        _log({"kind": "app", "local": bool(settings.local), "local_dir": local_dir})
        app.add_middleware(_watch(local_dir))
        return app

    _srv.create_app = create_app
    import thinkhow.web as _web

    if hasattr(_web, "create_app"):
        _web.create_app = create_app
except ModuleNotFoundError as _error:   # no thinkhow on the path (the smoke): no app
    _log({"kind": "no-thinkhow", "error": repr(_error)})
except Exception as _error:
    _log({"kind": "hook-error", "error": repr(_error)})


def _wrap_screenshots():
    try:
        from playwright.sync_api._generated import Page as _SyncPage

        _orig_sync = _SyncPage.screenshot

        def screenshot(self, *args, **kwargs):
            try:
                has = bool(self.evaluate("() => !!document.querySelector('#attach')"))
            except Exception:
                has = None
            _log({"kind": "screenshot", "attach": has})
            return _orig_sync(self, *args, **kwargs)

        _SyncPage.screenshot = screenshot
    except Exception as _error:
        _log({"kind": "screenshot-hook", "error": repr(_error)})
    try:
        from playwright.async_api._generated import Page as _AsyncPage

        _orig_async = _AsyncPage.screenshot

        async def ascreenshot(self, *args, **kwargs):
            try:
                has = bool(await self.evaluate("() => !!document.querySelector('#attach')"))
            except Exception:
                has = None
            _log({"kind": "screenshot", "attach": has})
            return await _orig_async(self, *args, **kwargs)

        _AsyncPage.screenshot = ascreenshot
    except Exception as _error:
        _log({"kind": "screenshot-hook", "error": repr(_error)})


_wrap_screenshots()
"""

# First in the <head> of every page, in every run.
WATCH_JS = r"""
(function () {
  var BIG = 32 * 1024 * 1024;
  var sizeOf = Object.getOwnPropertyDescriptor(Blob.prototype, "size").get;
  window.__ducuSize = function (blob) { return sizeOf.call(blob); };
  window.__ducuBeacon = function (what) {
    try { navigator.sendBeacon("/__ducu/" + what, ""); } catch (e) { /* the beacon is the test's only */ }
  };
  document.addEventListener("change", function (event) {
    var input = event.target;
    if (!input || input.id !== "document" || !input.files) { return; }
    for (var i = 0; i < input.files.length; i += 1) {
      var file = input.files[i];
      var size = window.__ducuSize(file);
      window.__ducuBeacon("chosen-" + (size > BIG ? "big" : "small") + "-" + encodeURIComponent(file.name));
    }
  }, true);
  function isDocument(input) {
    var url = typeof input === "string" ? input : (input && input.url) || String(input);
    return /\/document$/.test(url.split("?")[0].replace(/\/+$/, ""));
  }
  function bodyIsBig(init) {
    var body = init && init.body;
    var big = false;
    if (body && typeof FormData !== "undefined" && body instanceof FormData) {
      body.forEach(function (value) {
        if (value instanceof Blob && window.__ducuSize(value) > BIG) { big = true; }
      });
    } else if (body instanceof Blob && window.__ducuSize(body) > BIG) {
      big = true;
    }
    return big;
  }
  var realFetch = window.fetch;
  window.fetch = function (input, init) {
    if (!isDocument(input)) { return realFetch.apply(this, arguments); }
    window.__ducuBeacon(bodyIsBig(init) ? "fetch-big" : "fetch");
    return realFetch.apply(this, arguments).then(function (response) {
      window.__ducuBeacon("seen-" + response.status);
      if (window.__ducuOnResponse) { return window.__ducuOnResponse(response); }
      return response;
    });
  };
  var realOpen = XMLHttpRequest.prototype.open;
  XMLHttpRequest.prototype.open = function (method, url) {
    if (isDocument(String(url))) { window.__ducuBeacon("xhr"); }
    return realOpen.apply(this, arguments);
  };
})();
"""

# The page cannot see a file's size: every Blob over 1 MB reports 1 byte, so the page's 32 MiB check
# never refuses (the real size is still sent).
HIDE_SIZE_JS = r"""
(function () {
  Object.defineProperty(Blob.prototype, "size", {
    configurable: true,
    get: function () {
      var real = window.__ducuSize(this);
      if (real > 1000000) { window.__ducuBeacon("size-hidden"); return 1; }
      return real;
    }
  });
})();
"""

# A 413 the page receives WITHOUT ThinkHow's own fragment (Cloud Run's page) reaches the page's code as a 413
# whose body is a fragment with other words.
CLOUD_413_AS_FRAGMENT_JS = r"""
(function () {
  window.__ducuOnResponse = function (response) {
    if (response.status !== 413) { return response; }
    return response.clone().text().then(function (text) {
      if (text.indexOf('class="error"') >= 0) { return response; }
      window.__ducuBeacon("cloud413-replaced");
      return new Response('<p class="error">DUCU: інші слова</p>',
        { status: 413, headers: { "content-type": "text/html; charset=utf-8" } });
    });
  };
})();
"""

# `#attach` loses its aria-label as soon as the page is parsed (and whenever it gets one back).
NO_ARIA_JS = r"""
(function () {
  function strip() {
    var button = document.getElementById("attach");
    if (button && button.hasAttribute("aria-label")) {
      button.removeAttribute("aria-label");
      window.__ducuBeacon("aria-removed");
    }
  }
  document.addEventListener("DOMContentLoaded", function () {
    strip();
    new MutationObserver(strip).observe(document.documentElement,
      { attributes: true, subtree: true, childList: true });
  });
})();
"""


@dataclass
class Run:
    code: int
    out: str
    records: list[dict[str, Any]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.code == 0 and any(line.startswith("OK:") for line in self.out.splitlines())

    def kind(self, kind: str) -> list[dict[str, Any]]:
        return [r for r in self.records if r.get("kind") == kind]

    def docs(self) -> list[dict[str, Any]]:
        return self.kind("doc")

    def docs_named(self, name: str) -> list[dict[str, Any]]:
        return [r for r in self.docs() if name in r.get("files", [])]

    def beacons(self, what: str) -> int:
        return len([r for r in self.kind("beacon") if r.get("what") == what])

    def beacons_starting(self, prefix: str) -> list[str]:
        return [str(r["what"]) for r in self.kind("beacon") if str(r.get("what", "")).startswith(prefix)]


def run_smoke(rules: dict[str, Any] | None = None, breakage: str = "") -> Run:
    uv = shutil.which("uv")
    assert uv, "uv is not on PATH"
    with tempfile.TemporaryDirectory(prefix="ducu-") as tmp_name:
        tmp = Path(tmp_name)
        hook = tmp / "hook"
        hook.mkdir()
        (hook / "sitecustomize.py").write_text(SITECUSTOMIZE, encoding="utf-8")
        js = tmp / "page.js"
        js.write_text(WATCH_JS + breakage, encoding="utf-8")
        log = tmp / "log.jsonl"
        log.write_text("", encoding="utf-8")
        cwd = tmp / "cwd"
        cwd.mkdir()
        env = dict(os.environ)
        env["PYTHONPATH"] = os.pathsep.join(
            [str(hook), *[p for p in env.get("PYTHONPATH", "").split(os.pathsep) if p]]
        )
        env["DUCU_LOG"] = str(log)
        env["DUCU_RULES"] = json.dumps(rules or {})
        env["DUCU_JS"] = str(js)
        proc = subprocess.run(
            [uv, "run", "--project", str(REPO), "python", str(SCRIPT)],
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=480,
        )
        records = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]
    out = proc.stdout[-8000:] + "\n--- stderr ---\n" + proc.stderr[-8000:]
    return Run(proc.returncode, out, records)


@functools.lru_cache(maxsize=1)
def clean_run() -> Run:
    """The run with nothing broken (only the watchers), shared by every test that reads it."""
    return run_smoke()


def server_ran(run: Run, *, uploads: bool = True) -> None:
    assert not run.kind("hook-error"), f"the test's hook failed: {run.kind('hook-error')}\n" + run.out
    assert run.kind("app"), "the smoke never made an app through thinkhow.web.server.create_app\n" + run.out
    assert run.kind("js-served"), "the test's page script never reached a page\n" + run.out
    if uploads:
        assert run.docs(), "no POST …/document reached the app\n" + run.out
