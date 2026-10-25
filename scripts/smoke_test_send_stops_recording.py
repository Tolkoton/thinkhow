"""Browser check of task 206: «Говорити» → «Надіслати» → text in the field, nothing sent → «Надіслати» → sent.

Run: `uv run --with playwright==1.64.1 python scripts/smoke_test_send_stops_recording.py`.
Real uvicorn in local mode, real Chromium with a fake microphone (helpers of smoke_test_voice_dictation.py).
Asserts by itself.
"""

import os
import subprocess
import sys
import tempfile
import time
from typing import Any

from smoke_test_voice_dictation import CHROMIUM, FLAGS, LOCAL_TEXT, ROOT, free_port, sync_playwright, wait_for


def main() -> None:
    port, data = free_port(), tempfile.mkdtemp(prefix="thinkhow-send-")
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
        print("OK: «Надіслати» while recording: text in the field, nothing sent; the next press sent it")
    finally:
        server.terminate()
        server.wait(timeout=10)


def walk(page: Any, base: str) -> None:
    page.goto(base + "/language")
    page.select_option('select[name="code"]', "uk-UA")
    page.click('button[type="submit"]')
    page.wait_for_url(base + "/")
    page.fill('input[name="title"]', "Надіслати під час запису")
    page.click('form[action="/topics"] button[type="submit"]')
    page.wait_for_selector("#mic")
    print("topic page:", page.url)
    posts: list[str] = []
    page.on("request", lambda r: posts.append(r.url.rsplit("/", 1)[-1]) if r.method == "POST" else None)
    page.click("#mic")
    page.wait_for_function("document.getElementById('mic-state').textContent.startsWith('Запис')")
    print("«Говорити»: recording")
    time.sleep(2)
    page.click("#send")
    print("«Надіслати» pressed while recording")
    page.wait_for_function(
        f"document.querySelector('textarea').value.includes({LOCAL_TEXT!r})", timeout=15000
    )
    time.sleep(1)
    assert posts == ["voice"], posts
    assert page.locator("article.turn").count() == 0, page.locator("article.turn").all_inner_texts()
    assert page.text_content("#error") == "", page.text_content("#error")
    assert page.text_content("#mic-state") == "", page.text_content("#mic-state")
    print("field:", page.input_value("textarea"), "| POSTs:", posts, "| turns: 0 | error: none")
    page.screenshot(path=str(ROOT / ".engine/artifacts/send-stops-recording/text-in-field.png"))
    page.fill("textarea", page.input_value("textarea") + " — виправлено")
    page.click("#send")
    page.wait_for_selector("article.turn.model", timeout=15000)
    turns = page.locator("article.turn").all_inner_texts()
    assert posts == ["voice", "reply"], posts
    assert any(LOCAL_TEXT + " — виправлено" in t for t in turns), turns
    print("second «Надіслати»: POSTs:", posts, "| turns:", len(turns), "| the corrected text was sent")
    page.screenshot(path=str(ROOT / ".engine/artifacts/send-stops-recording/sent.png"))


if __name__ == "__main__":
    main()
