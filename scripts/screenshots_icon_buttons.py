"""Screenshots and checks of task 207: the buttons are icons, the mic shows its state without words.

Run: `uv run --with playwright==1.64.1 python scripts/screenshots_icon_buttons.py --out <dir>`.
Real uvicorn in local mode, real Chromium with a fake microphone (helpers of smoke_test_voice_dictation.py).
Shoots «Мої теми» with the delete confirmation open, the topic page idle, recording, recognizing (the /voice
request held) and waiting for the answer (the /reply request held) — then lets both go and checks the
dictated text reached the field, the reply was sent and answered, and a topic was deleted. Ends with `OK:`.
"""

import argparse
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from smoke_test_voice_dictation import CHROMIUM, FLAGS, LOCAL_TEXT, ROOT, free_port, sync_playwright, wait_for

PHONE: dict[str, Any] = {
    "viewport": {"width": 390, "height": 844},
    "device_scale_factor": 2,
    "is_mobile": True,
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="screens", help="the directory for the PNGs")
    out = Path(parser.parse_args().out)
    out.mkdir(parents=True, exist_ok=True)
    port, data = free_port(), tempfile.mkdtemp(prefix="thinkhow-icons-")
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
            browser = p.chromium.launch(executable_path=CHROMIUM, args=FLAGS)
            page = browser.new_context(permissions=["microphone"], **PHONE).new_page()
            walk(page, base, out)
            browser.close()
        print(
            f"OK: icons only; recording, recognizing and pending visible without words; screenshots in {out}"
        )
    finally:
        server.terminate()
        server.wait(timeout=10)


def walk(page: Any, base: str, out: Path) -> None:
    page.goto(base + "/language")
    page.select_option('select[name="code"]', "uk-UA")
    page.click('form[action="/language"] button[type="submit"]')
    page.wait_for_url(base + "/")
    for title in ("Кав'ярня: клієнти не повертаються", "Тест — непотрібна розмова"):
        page.goto(base + "/")
        page.fill('input[name="title"]', title)
        page.click('button[aria-label="Створити"]')
        page.wait_for_selector("#mic")
    no_words(page)
    page.screenshot(path=str(out / "topic-idle.png"), full_page=True)
    dictate(page, out)
    send(page, out)
    delete_from_list(page, base, out)


def no_words(page: Any) -> None:
    """Every visible button and summary shows no words and has an aria-label."""
    for el in page.locator("button:visible, summary:visible").all():
        label = el.get_attribute("aria-label")
        assert label and el.inner_text().strip() == "", (label, el.inner_text())


def dictate(page: Any, out: Path) -> None:
    held: list[Any] = []
    page.route("**/voice", lambda route: held.append(route))
    page.click("#mic")
    page.wait_for_function("document.getElementById('mic').dataset.state === 'recording'")
    time.sleep(1.5)
    assert page.get_attribute("#mic", "aria-pressed") == "true"
    page.screenshot(path=str(out / "topic-recording.png"), full_page=True)
    page.click("#mic")
    page.wait_for_function("document.getElementById('mic').dataset.state === 'recognizing'")
    assert page.is_visible("#mic .spinner") and not page.is_visible("#mic .i-mic")
    page.screenshot(path=str(out / "topic-recognizing.png"), full_page=True)
    while not held:
        page.wait_for_timeout(100)
    held[0].continue_()
    page.unroute("**/voice")
    page.wait_for_function(
        f"document.querySelector('textarea').value.includes({LOCAL_TEXT!r})", timeout=15000
    )
    assert page.get_attribute("#mic", "data-state") == ""
    print("voice: recording → recognizing → text in the field:", page.input_value("textarea"))


def send(page: Any, out: Path) -> None:
    held: list[Any] = []
    page.route("**/reply", lambda route: held.append(route))
    page.click("#send")
    while not held:
        page.wait_for_timeout(100)
    assert page.is_visible("#pending .spinner") and page.is_disabled("#send")
    page.screenshot(path=str(out / "topic-pending.png"), full_page=True)
    held[0].continue_()
    page.unroute("**/reply")
    page.wait_for_selector("article.turn.model", timeout=15000)
    assert not page.is_visible("#pending")
    page.screenshot(path=str(out / "topic-answered.png"), full_page=True)
    print(
        "send: pending spinner while /reply is held; answered:", page.locator("article.turn").count(), "turns"
    )


def delete_from_list(page: Any, base: str, out: Path) -> None:
    page.goto(base + "/")
    no_words(page)
    page.screenshot(path=str(out / "home.png"), full_page=True)
    item = page.locator("ul.topics li", has_text="Тест — непотрібна розмова")
    item.locator('summary[aria-label="Видалити"]').click()
    page.screenshot(path=str(out / "home-delete-confirm.png"), full_page=True)
    item.locator('button[aria-label="Так, видалити"]').click()
    page.wait_for_url(base + "/")
    assert "Тест — непотрібна розмова" not in page.locator("ul.topics").first.inner_text()
    page.screenshot(path=str(out / "home-after-delete.png"), full_page=True)
    print("delete: the bin, then the red bin; the topic is gone from the list")


if __name__ == "__main__":
    main()
