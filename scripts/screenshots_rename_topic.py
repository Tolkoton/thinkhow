"""Screenshots and checks of task 209: renaming a topic in the list, its only place since 211.

Run: `PYTHONPATH=src uv run --with playwright==1.64.1 python scripts/screenshots_rename_topic.py --out <dir>`
(Playwright is no project dependency). Chromium: `THINKHOW_CHROMIUM`, else the cached chromium-1208.
Puts another person's topic into the local `users` bucket, makes two own topics in the browser, renames one
in the list by Enter and one by the check icon (its page has no pencil), checks Esc puts the old
title back, an empty title is not saved, both new titles stand in both places after a reload, the
conversation is untouched, and the other person's topic, which the owner may read, has no pencil and
refuses a rename with 404. Leaves the PNGs in <dir>, ends with `OK:`.
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
OLD = ("Кав'ярня: клієнти не повертаються", "Нова розмова")
NEW = ("Кав'ярня: чому не повертаються постійні гості", "Переїзд до Львова")
FOREIGN = ("someone-else", "t-0123456789ab", "Чужа тема")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="screens", help="the directory for the PNGs")
    out = Path(parser.parse_args().out)
    out.mkdir(parents=True, exist_ok=True)
    port, data = free_port(), Path(tempfile.mkdtemp(prefix="thinkhow-rename-"))
    foreign = data / "users" / FOREIGN[0] / FOREIGN[1] / "conversation.md"
    foreign.parent.mkdir(parents=True)
    foreign.write_text(f"<!-- thinkhow:format 1 -->\n# {FOREIGN[2]}\n\n<!-- thinkhow:session 1 -->\n")
    env = {
        **os.environ,
        "PYTHONPATH": str(ROOT / "src"),
        "THINKHOW_LOCAL": "true",
        "THINKHOW_LOCAL_DIR": str(data),
        "THINKHOW_OWNER_EMAIL": "owner@localhost",
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
            topics = [make_topic(page, base, title) for title in OLD]
            turns = conversation_body(users / topics[0])
            in_list(page, base, topics[0], out)
            assert conversation_body(users / topics[0]) == turns, "the conversation changed"
            on_page(browser, base, topics[1], out)
            after_reload(page, base, topics, out)
            not_foreign(page, base, foreign, out)
            browser.close()
        print(
            f"OK: renamed in the list, no pencil on the page, kept on reload, empty, foreign refused: {out}"
        )
    finally:
        server.terminate()
        server.wait(timeout=10)


def make_topic(page: Any, base: str, title: str) -> str:
    page.goto(base + "/")
    page.fill('form[action="/topics"] input[name="title"]', title)
    page.click('form[action="/topics"] button[type="submit"]')
    page.wait_for_selector("#send")
    page.fill("textarea", "Хочу подумати над цим.")
    page.click("#send")
    page.wait_for_function("document.querySelectorAll('article.turn').length === 2", timeout=15000)
    return str(page.url.rsplit("/", 1)[-1])


def in_list(page: Any, base: str, topic_id: str, out: Path) -> None:
    page.goto(base + "/")
    item = page.locator("ul.topics").first.locator("li", has=page.locator(f'a[href$="/{topic_id}"]'))
    field = item.locator('details.rename input[name="new_title"]')
    assert not field.is_visible(), "the field shows before the pencil is pressed"
    page.screenshot(path=str(out / "home-pencil.png"))
    item.locator("details.rename summary").click()
    assert field.is_visible() and not item.locator("a").is_visible(), "the title did not become a field"
    assert field.input_value() == OLD[0] and field.evaluate("f => f === document.activeElement")
    field.fill("Щось інше")
    field.press("Escape")
    assert not field.is_visible() and item.locator("a").inner_text() == OLD[0], "Esc did not cancel"
    item.locator("details.rename summary").click()
    assert field.input_value() == OLD[0], "Esc did not put the old title back into the field"
    field.fill("   ")
    field.press("Enter")
    assert page.url == base + "/" and item.locator("a").inner_text() == OLD[0], "an empty title was saved"
    print("empty title refused in the list")
    field.fill(NEW[0])
    page.screenshot(path=str(out / "home-rename-field.png"))
    field.press("Enter")
    page.wait_for_load_state()
    assert item.locator("a").inner_text() == NEW[0], item.locator("a").inner_text()
    page.screenshot(path=str(out / "home-after-rename.png"))


def on_page(browser: Any, base: str, topic_id: str, out: Path) -> None:
    """Task 211: the page has no pencil any more; the second topic is renamed in the list by the check."""
    page = new_page(browser, PHONE, "light")
    page.goto(f"{base}/topics/{UID}/{topic_id}")
    assert page.locator("details.rename").count() == 0, "the topic page still has the pencil"
    page.screenshot(path=str(out / "topic-no-pencil-phone.png"))
    page.goto(base + "/")
    item = page.locator("ul.topics").first.locator("li", has=page.locator(f'a[href$="/{topic_id}"]'))
    item.locator("details.rename summary").click()
    field = item.locator('details.rename input[name="new_title"]')
    assert field.input_value() == OLD[1]
    field.fill(NEW[1])
    page.screenshot(path=str(out / "home-rename-field-phone.png"))
    item.locator('details.rename button[aria-label="Зберегти"]').click()
    page.wait_for_url(base + "/")
    assert item.locator("a").inner_text() == NEW[1], item.locator("a").inner_text()
    page.context.close()


def after_reload(page: Any, base: str, topics: list[str], out: Path) -> None:
    page.goto(base + "/")
    page.reload()
    mine = page.locator("ul.topics").first.inner_text()
    assert NEW[0] in mine and NEW[1] in mine and OLD[0] not in mine and OLD[1] not in mine, mine
    for topic_id, title in zip(topics, NEW, strict=True):
        page.goto(f"{base}/topics/{UID}/{topic_id}")
        page.reload()
        assert page.locator("h1").inner_text() == title
    page.goto(base + "/")
    page.screenshot(path=str(out / "home-after-reload.png"))
    print("after a reload:", " | ".join(NEW))


def not_foreign(page: Any, base: str, foreign: Path, out: Path) -> None:
    uid, topic_id, title = FOREIGN
    status = page.goto(f"{base}/topics/{uid}/{topic_id}").status
    assert status == 200, (status, page.content())
    assert page.locator("h1").inner_text() == title and page.locator("details.rename").count() == 0
    page.screenshot(path=str(out / "foreign-topic-no-pencil.png"))
    before = foreign.read_text()
    answer = page.request.post(f"{base}/topics/{uid}/{topic_id}/rename", form={"new_title": "Моя тепер"})
    assert answer.status == 404 and foreign.read_text() == before, answer.status
    print("foreign topic: no pencil, rename answered", answer.status, answer.text())


def conversation_body(folder: Path) -> list[str]:
    return (folder / "conversation.md").read_text().split("\n")[2:]


if __name__ == "__main__":
    main()
