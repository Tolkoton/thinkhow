"""Bug 001 (task 210): after a deploy the browser kept the old `conversation.js`; the paperclip did nothing.

The deploy is played out in one browser profile at one address: first the old image — its page asks
for `/static/conversation.js` and `/static/style.css` without a version, the files dated as `git archive`
dates them (the old commit's time) — then the real app of this tree. The person opens their topic and
clicks the real `#attach`: the file chooser must open, and the new stylesheet must be in force. The version on
every /static URL is checked without a browser in `test_static_version.py`.
"""

from __future__ import annotations

import os
import socket
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest
import uvicorn
from starlette.applications import Starlette
from starlette.responses import HTMLResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from thinkhow.web.app import CARDS_DIR, build_deps
from thinkhow.web.server import create_app

sync_api = pytest.importorskip("playwright.sync_api")

OLD_PAGE = """<!doctype html><html><head><link rel="stylesheet" href="/static/style.css"></head>
<body><script src="/static/conversation.js"></script></body></html>"""
OLD_JS = "/* the old image's script: no paperclip */\n"
OLD_CSS = "body { --stale: old-image; }\n"
THREE_DAYS = 3 * 24 * 3600


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@contextmanager
def _serve(app: Starlette, port: int) -> Iterator[str]:
    server = uvicorn.Server(uvicorn.Config(app, port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        time.sleep(0.05)
    try:
        yield f"http://localhost:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=10)


def _old_image(static: Path) -> Starlette:
    static.mkdir()
    for name, body in (("conversation.js", OLD_JS), ("style.css", OLD_CSS)):
        (static / name).write_text(body, encoding="utf-8")
        old = time.time() - THREE_DAYS
        os.utime(static / name, (old, old))
    return Starlette(
        routes=[
            Route("/", lambda request: HTMLResponse(OLD_PAGE)),
            Mount("/static", StaticFiles(directory=static)),
        ]
    )


def test_after_a_deploy_the_paperclip_opens_the_file_chooser(tmp_path: Path) -> None:
    port = _free_port()
    env = {"THINKHOW_LOCAL": "true", "THINKHOW_LOCAL_DIR": str(tmp_path / "data")}
    with sync_api.sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(str(tmp_path / "profile"))
        page = browser.new_page()
        with _serve(_old_image(tmp_path / "old-static"), port) as base:
            page.goto(base + "/")
        with _serve(create_app(build_deps(env, CARDS_DIR)), port) as base:
            page.goto(base + "/language")
            page.select_option('select[name="code"]', "uk-UA")
            page.click('form[action="/language"] button[type="submit"]')
            page.wait_for_url(base + "/")
            page.fill('input[name="title"]', "Тест скріпки")
            page.click('button[aria-label="Створити"]')
            page.wait_for_selector("#attach")
            stale = page.evaluate("getComputedStyle(document.body).getPropertyValue('--stale')")
            try:
                with page.expect_file_chooser(timeout=3000):
                    page.locator("#attach").click()
                opened = True
            except sync_api.TimeoutError:
                opened = False
        browser.close()
    assert opened, (
        "the paperclip opened no file chooser: the old conversation.js came from the browser's cache"
    )
    assert stale == "", f"the old image's style.css came from the browser's cache: --stale={stale!r}"
