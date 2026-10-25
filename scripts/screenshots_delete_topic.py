"""Screenshots and checks of task 204: deleting a topic from the list and from its page (uvicorn + Chromium).

Run: `PYTHONPATH=src uv run --with playwright==1.64.1 python scripts/screenshots_delete_topic.py --out <dir>`
(Playwright is no project dependency). Chromium: `THINKHOW_CHROMIUM`, else the cached chromium-1208.
Makes three topics in the browser, each with one reply of the local model (so map.json and routing.json
exist), deletes one from the list and one from its page, each through the one confirmation, and checks the
folder of a deleted topic in the local `users` bucket is empty while the kept topic keeps its files. Leaves
the PNGs in <dir>, ends with `OK:`.
"""

import argparse
import importlib
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from screenshots_minimal_design import CHROMIUM, DESKTOP, PHONE, free_port, new_page, wait_for

sync_playwright = importlib.import_module("playwright.sync_api").sync_playwright

ROOT = Path(__file__).resolve().parents[1]
UID = "local-owner"
TITLES = ("Кав'ярня: клієнти не повертаються", "Тест — непотрібна розмова", "Ще одна спроба")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="screens", help="the directory for the PNGs")
    out = Path(parser.parse_args().out)
    out.mkdir(parents=True, exist_ok=True)
    port, data = free_port(), Path(tempfile.mkdtemp(prefix="thinkhow-delete-"))
    env = {
        **os.environ,
        "PYTHONPATH": str(ROOT / "src"),
        "THINKHOW_LOCAL": "true",
        "THINKHOW_LOCAL_DIR": str(data),
    }
    command = [sys.executable, "-m", "uvicorn", "thinkhow.web.app:app", "--port", str(port)]
    server = subprocess.Popen(command, cwd=ROOT, env=env)
    base = f"http://localhost:{port}"
    users = data / "users" / UID
    try:
        wait_for(base + "/language")
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=CHROMIUM)
            page = new_page(browser, DESKTOP, "light")
            page.goto(base + "/language")
            page.select_option("select", "uk-UA")
            page.click('button[type="submit"]')
            topics = {title: make_topic(page, base, title) for title in TITLES}
            print_files("before", users)
            from_list(page, base, topics[TITLES[1]], users, out)
            from_page(browser, base, topics[TITLES[2]], users, out)
            kept = files(users / topics[TITLES[0]])
            assert {"conversation.md", "map.json", "routing.json"} <= set(kept), kept
            print_files("after", users)
            browser.close()
        print(f"OK: deleted from the list and from the page, folders empty, the kept topic intact; in {out}")
    finally:
        server.terminate()
        server.wait(timeout=10)


def make_topic(page: Any, base: str, title: str) -> str:
    page.goto(base + "/")
    page.fill('input[name="title"]', title)
    page.click('form[action="/topics"] button[type="submit"]')
    page.wait_for_selector("#send")
    page.fill("textarea", "Хочу подумати над цим.")
    page.click("#send")
    page.wait_for_function("document.querySelectorAll('article.turn').length === 2", timeout=15000)
    return str(page.url.rsplit("/", 1)[-1])


def from_list(page: Any, base: str, topic_id: str, users: Path, out: Path) -> None:
    page.goto(base + "/")
    item = page.locator("ul.topics li", has=page.locator(f'a[href$="/{topic_id}"]'))
    confirm = item.locator('button:has-text("Так, видалити")')
    assert not confirm.is_visible(), "the confirmation shows before «Видалити» is pressed"
    page.screenshot(path=str(out / "home-delete-button.png"))
    item.locator("summary").click()
    assert confirm.is_visible()
    text = item.locator("details.delete p").inner_text()
    assert TITLES[1] in text, text
    print("list confirmation:", text)
    page.screenshot(path=str(out / "home-delete-confirm.png"))
    confirm.click()
    page.wait_for_url(base + "/")
    assert TITLES[1] not in page.locator("ul.topics").first.inner_text()
    assert files(users / topic_id) == [], files(users / topic_id)
    page.screenshot(path=str(out / "home-after-delete.png"))


def from_page(browser: Any, base: str, topic_id: str, users: Path, out: Path) -> None:
    page = new_page(browser, PHONE, "light")
    page.goto(f"{base}/topics/{UID}/{topic_id}")
    page.locator("details.delete summary").click()
    text = page.locator("details.delete p").inner_text()
    assert TITLES[2] in text, text
    print("page confirmation:", text)
    page.screenshot(path=str(out / "topic-delete-confirm-phone.png"), full_page=True)
    page.click('button:has-text("Так, видалити")')
    page.wait_for_url(base + "/")
    assert TITLES[2] not in page.locator("ul.topics").first.inner_text()
    assert files(users / topic_id) == [], files(users / topic_id)
    assert page.goto(f"{base}/topics/{UID}/{topic_id}").status == 404
    page.context.close()


def files(folder: Path) -> list[str]:
    return sorted(p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file())


def print_files(when: str, users: Path) -> None:
    print(f"files {when}:")
    for name in files(users):
        print("  users/" + UID + "/" + name)


if __name__ == "__main__":
    main()
