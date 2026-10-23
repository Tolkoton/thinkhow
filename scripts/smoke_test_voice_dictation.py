"""Smoke of slice voice-dictation: real uvicorn in local mode + real Chromium with a fake microphone.

Run: `uv run --with playwright==1.64.1 python scripts/smoke_test_voice_dictation.py` (Playwright is no project
dependency). Chromium: `THINKHOW_CHROMIUM`, else the cached chromium-1208. Asserts by itself; prints steps.
"""

import importlib
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import httpx

# Playwright is no project dependency (run with `uv run --with playwright…`), so it is loaded by name.
sync_playwright = importlib.import_module("playwright.sync_api").sync_playwright

ROOT = Path(__file__).resolve().parents[1]
LOCAL_TEXT = "(локальний режим) розпізнаний текст"
FLAGS = ["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"]
CACHED = Path.home() / ".cache/ms-playwright/chromium-1208/chrome-linux64/chrome"
CHROMIUM = os.environ.get("THINKHOW_CHROMIUM", str(CACHED))


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def main() -> None:
    port, data = free_port(), tempfile.mkdtemp(prefix="thinkhow-voice-")
    env = {
        **os.environ,
        "PYTHONPATH": str(ROOT / "src"),
        "THINKHOW_LOCAL": "true",
        "THINKHOW_LOCAL_DIR": data,
        "THINKHOW_OWNER_EMAIL": "owner@localhost",
    }
    command = [sys.executable, "-m", "uvicorn", "thinkhow.web.app:app", "--port", str(port)]
    server = subprocess.Popen(command, cwd=ROOT, env=env)
    base = f"http://localhost:{port}"
    try:
        wait_for(base + "/language")
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=CHROMIUM, args=FLAGS)
            page = browser.new_context(permissions=["microphone"]).new_page()
            walk(page, base)
            browser.close()
        print(
            f"OK: language → topic → microphone → text in the field → sent and answered; files under {data}"
        )
    finally:
        server.terminate()
        server.wait(timeout=10)


def walk(page: Any, base: str) -> None:
    """Flow: first visit → language → a topic → speak → the text in the field → send → the answer."""
    page.goto(base + "/")
    assert page.url.endswith("/language"), page.url
    print("first visit: / → /language")
    page.select_option('select[name="code"]', "uk-UA")
    page.click('button[type="submit"]')
    page.wait_for_url(base + "/")
    print("language uk-UA chosen")
    page.fill('input[name="title"]', "Голос")
    page.click('form[action="/topics"] button[type="submit"]')
    page.wait_for_selector("#mic")
    print("topic page:", page.url)
    voice: list[dict[str, Any]] = []
    page.on("response", lambda r: record(r, voice))
    page.click("#mic")
    page.wait_for_function("document.getElementById('mic-state').textContent.startsWith('Запис')")
    time.sleep(2)
    page.click("#mic")
    page.wait_for_function(
        f"document.querySelector('textarea').value.includes({LOCAL_TEXT!r})", timeout=15000
    )
    print("field after the microphone:", page.input_value("textarea"))
    # an empty body gets 400, so a 200 means the recording arrived (Playwright hides Blob bodies)
    assert voice and voice[0]["type"].startswith("audio/webm") and voice[0]["status"] == 200, voice
    print("POST …/voice:", voice[0])
    page.click("#send")
    page.wait_for_selector("article.turn.model", timeout=15000)
    turns = page.locator("article.turn").all_inner_texts()
    assert any(LOCAL_TEXT in t for t in turns), turns
    print("sent; the page shows the turn and the facilitator's answer:", len(turns), "turns")


def record(response: Any, voice: list[dict[str, Any]]) -> None:
    if response.url.endswith("/voice"):
        voice.append({"type": response.request.headers.get("content-type", ""), "status": response.status})


def wait_for(url: str) -> None:
    for _ in range(100):
        try:
            httpx.get(url)
            return
        except httpx.ConnectError:
            time.sleep(0.1)
    raise AssertionError("uvicorn did not start")


if __name__ == "__main__":
    main()
