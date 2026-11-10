"""Smoke of slice document-upload (task 311): the paperclip on a real page, in a real browser.

Run: `uv run python scripts/smoke_test_document_upload.py --out <dir>`.
Real uvicorn in local mode, real Chromium. Shoots the topic page with the paperclip, uploads `resume.pdf`
and `resume.docx` (each → a `📎` turn and an answer), reloads (both turns stay, `documents.json` holds both
texts, the local model's map item holds the document's text — the frame reached the model), then the four
refusals: a scan
(`err_document_unreadable`), a file over 32 MiB (not sent), Cloud Run's own 413, the topic's limit
(`err_document_too_large`) — none adds a turn. Ends with `OK:`.
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright
from smoke_test_voice_dictation import CHROMIUM, ROOT, free_port, wait_for

FILES = ROOT / "tests" / "contract" / "document_upload" / "files"
UK = json.loads((ROOT / "src" / "thinkhow" / "web" / "locales" / "uk.json").read_text(encoding="utf-8"))
LIMIT = 32 * 1024 * 1024


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="screens", help="the directory for the PNGs")
    out = Path(parser.parse_args().out)
    out.mkdir(parents=True, exist_ok=True)
    port, data = free_port(), tempfile.mkdtemp(prefix="thinkhow-documents-")
    env = {
        **os.environ,
        "PYTHONPATH": str(ROOT / "src"),
        "THINKHOW_LOCAL": "true",
        "THINKHOW_LOCAL_DIR": data,
    }
    command = [sys.executable, "-m", "uvicorn", "thinkhow.web.app:app", "--port", str(port)]
    server = subprocess.Popen(command, cwd=ROOT, env=env)
    base = f"http://localhost:{port}"
    try:
        wait_for(base + "/language")
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=CHROMIUM)
            page = browser.new_context(
                viewport={"width": 390, "height": 844}, device_scale_factor=2
            ).new_page()
            walk(page, base, out, Path(data))
            browser.close()
        print(
            f"OK: the paperclip uploads PDF and DOCX, both stay after reload, 4 refusals add no turn; {out}"
        )
    finally:
        server.terminate()
        server.wait(timeout=10)


def walk(page: Any, base: str, out: Path, data: Path) -> None:
    page.goto(base + "/language")
    page.select_option('select[name="code"]', "uk-UA")
    page.click('form[action="/language"] button[type="submit"]')
    page.wait_for_url(base + "/")
    page.fill('input[name="title"]', "Пошук роботи: куди рухатись далі")
    page.click('button[aria-label="Створити"]')
    page.wait_for_selector("#attach")
    attach = page.locator("#attach")
    assert attach.get_attribute("aria-label") == UK["upload_document"] and attach.inner_text().strip() == ""
    page.screenshot(path=str(out / "topic-with-paperclip.png"), full_page=True)
    print("page: #attach with aria-label", attach.get_attribute("aria-label"))
    for n, name in enumerate(("resume.pdf", "resume.docx"), start=1):
        upload(page, FILES / name, 2 * n)
        assert page.locator("article.turn.user .text").nth(n - 1).inner_text() == f"📎 {name}"
        print(f"{name}: a 📎 turn and an answer —", page.locator("article.turn").count(), "turns")
    page.screenshot(path=str(out / "topic-two-documents.png"), full_page=True)
    page.reload()
    texts = page.locator("article.turn.user .text").all_inner_texts()
    assert texts == ["📎 resume.pdf", "📎 resume.docx"], texts
    topic = next(data.glob("users/*/t-*/documents.json")).parent
    entries = json.loads((topic / "documents.json").read_text(encoding="utf-8"))["entries"]
    assert [e["name"] for e in entries] == ["resume.pdf", "resume.docx"]
    assert "Monobank" in entries[0]["text"] and "Олена Коваль" in entries[1]["text"], entries
    assert "Monobank" in (topic / "map.json").read_text(encoding="utf-8"), "the model never saw the document"
    print("reload: both turns stay; documents.json holds both texts; the model's map item holds the text")
    refusals(page, topic)
    page.screenshot(path=str(out / "topic-refused.png"), full_page=True)


def upload(page: Any, file: Path, turns: int) -> None:
    page.set_input_files("#document", str(file))
    page.wait_for_function(f"document.querySelectorAll('article.turn').length >= {turns}", timeout=20000)


def refusals(page: Any, topic: Path) -> None:
    count = page.locator("article.turn").count()
    page.set_input_files("#document", str(FILES / "scan.pdf"))
    shows(page, UK["err_document_unreadable"])
    print("scan.pdf: err_document_unreadable shown")
    sent: list[str] = []
    page.on("request", lambda r: sent.append(r.url) if r.url.endswith("/document") else None)
    big = {"name": "big.txt", "mimeType": "text/plain", "buffer": b"a" * (LIMIT + 1)}
    page.set_input_files("#document", files=[big])
    shows(page, UK["js_document_too_large"])
    assert sent == [], sent
    print("over 32 MiB: js_document_too_large shown, nothing sent")
    page.route(
        "**/document", lambda route: route.fulfill(status=413, body="<html><h1>413 Too Large</h1></html>")
    )
    page.set_input_files("#document", str(FILES / "resume.pdf"))
    shows(page, UK["js_document_too_large"])
    page.unroute("**/document")
    print("Cloud Run's 413: js_document_too_large shown")
    long = {"name": "long.txt", "mimeType": "text/plain", "buffer": ("я" * 199_990).encode("utf-8")}
    page.set_input_files("#document", files=[long])
    shows(page, UK["err_document_too_large"])
    print("the topic's limit: err_document_too_large shown")
    page.reload()
    assert page.locator("article.turn").count() == count, "a refusal added a turn"
    assert len(json.loads((topic / "documents.json").read_text(encoding="utf-8"))["entries"]) == 2


def shows(page: Any, text: str) -> None:
    page.wait_for_function(
        f"document.getElementById('error').textContent === {json.dumps(text)}", timeout=15000
    )
    page.evaluate("document.getElementById('error').textContent = ''")


if __name__ == "__main__":
    main()
