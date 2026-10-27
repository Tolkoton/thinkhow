"""Screenshots and checks of task 208: the interface speaks the language the person chose.

Run: `uv run --with playwright==1.64.1 python scripts/screenshots_interface_language.py --out <dir>`.
For each language a fresh uvicorn in local mode and a Chromium whose browser language is that language:
the language page before the choice (in the browser's language), the choice, a topic with one reply and its
answer, «Мої теми» with the delete confirmation open, the language page after the choice. Every page is
checked against the language's catalog and for the absence of the Ukrainian words. Ends with `OK:`.
"""

import argparse
import os
import re
import subprocess
import sys
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from smoke_test_voice_dictation import CHROMIUM, FLAGS, ROOT, free_port, sync_playwright, wait_for

sys.path.insert(0, str(ROOT / "src"))
from thinkhow.web import ui_text  # noqa: E402

# code, browser locale, a topic title and a reply in that language
LANGUAGES = [
    ("uk-UA", "uk-UA", "Кав'ярня: клієнти не повертаються", "Люди приходять раз і більше не повертаються."),
    ("en-US", "en-US", "Café: customers do not come back", "People come once and never return."),
    ("ja-JP", "ja-JP", "カフェ：お客さんが戻ってこない", "一度来た人が二度と来ません。"),
    ("ar-EG", "ar-EG", "المقهى: الزبائن لا يعودون", "يأتي الناس مرة واحدة ولا يعودون."),
]
UKRAINIAN = re.compile(r"Мої теми|Нова тема|Модель мислення|Сесія|Фасилітатор|Якою мовою|змінити")
DESKTOP: dict[str, Any] = {"viewport": {"width": 1000, "height": 760}}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="screens", help="the directory for the PNGs")
    out = Path(parser.parse_args().out)
    out.mkdir(parents=True, exist_ok=True)
    for code, locale, title, text in LANGUAGES:
        one_language(out, code, locale, title, text)
    print(f"OK: {len(LANGUAGES)} languages, every page in the chosen one; screenshots in {out}")


def one_language(out: Path, code: str, locale: str, title: str, text: str) -> None:
    port, data = free_port(), tempfile.mkdtemp(prefix="thinkhow-lang-")
    env = {
        **os.environ,
        "PYTHONPATH": str(ROOT / "src"),
        "THINKHOW_LOCAL": "true",
        "THINKHOW_LOCAL_DIR": data,
    }
    command = [sys.executable, "-m", "uvicorn", "thinkhow.web.app:app", "--port", str(port)]
    server = subprocess.Popen(
        command, cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    base = f"http://localhost:{port}"
    try:
        wait_for(base + "/language")
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=CHROMIUM, args=FLAGS)
            page = browser.new_context(locale=locale, **DESKTOP).new_page()
            walk(page, base, out / code, code, title, text)
            browser.close()
    finally:
        server.terminate()
        server.wait(timeout=10)


def walk(page: Any, base: str, out: Path, code: str, title: str, text: str) -> None:
    out.mkdir(parents=True, exist_ok=True)
    name = ui_text.catalog_name(code)
    words = ui_text.texts(name)
    page.goto(base + "/")
    assert page.url.endswith("/language"), page.url
    check(page, words, name, "language before the choice")
    page.screenshot(path=str(out / "language-before-choice.png"), full_page=True)
    page.select_option('select[name="code"]', code)
    page.click('form[action="/language"] button[type="submit"]')
    page.wait_for_url(base + "/")
    for topic in (title, "Test"):
        page.goto(base + "/")
        page.fill('input[name="title"]', topic)
        page.click('form[action="/topics"] button[type="submit"]')
        page.wait_for_selector("#send")
    page.goto(base + "/")
    page.click(f'ul.topics a:text("{title}")')
    page.fill("textarea", text)
    page.click("#send")
    page.wait_for_selector("article.turn.model", timeout=15000)
    check(page, words, name, "topic")
    assert page.inner_text("section.session h2").startswith(words["session"].format(n=1)), code
    assert words["thinking_model"] in page.inner_text("aside.method"), code
    page.screenshot(path=str(out / "topic.png"), full_page=True)
    page.goto(base + "/")
    check(page, words, name, "my topics")
    assert page.inner_text("h1") == words["my_topics"], code
    page.locator("ul.topics li", has_text="Test").locator("summary").click()
    assert words["delete_confirm"].format(title="Test") in page.inner_text("ul.topics"), code
    page.screenshot(path=str(out / "my-topics.png"), full_page=True)
    page.goto(base + "/language")
    check(page, words, name, "language")
    page.screenshot(path=str(out / "language.png"), full_page=True)
    print(f"{code}: language page before the choice, topic, my topics, language — all in «{name}»")


def check(page: Any, words: Mapping[str, str], name: str, where: str) -> None:
    assert page.get_attribute("html", "lang") == name, (where, page.get_attribute("html", "lang"))
    assert page.get_attribute("html", "dir") == ui_text.direction(name), where
    body = page.inner_text("main") + " ".join(
        el.get_attribute("aria-label") or "" for el in page.locator("[aria-label]").all()
    )
    if name != "uk":
        assert not UKRAINIAN.search(body), (where, UKRAINIAN.search(body))
    if where.startswith("language"):
        assert words["language_prompt"] in body, where


if __name__ == "__main__":
    main()
