"""Screenshots and checks of slice minimal-design: real uvicorn in local mode + real Chromium.

Run: `uv run --with playwright==1.64.1 python scripts/screenshots_minimal_design.py --out <dir>`
(Playwright is no project dependency). Chromium: `THINKHOW_CHROMIUM`, else the cached chromium-1208.
Asserts by itself (Seams 1–3 of .engine/slices/minimal-design.md), prints steps, leaves the PNGs in <dir>,
ends with an `OK:` line.
"""

import argparse
import importlib
import os
import socket
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx

# Playwright is no project dependency (run with `uv run --with playwright…`), so it is loaded by name.
sync_playwright = importlib.import_module("playwright.sync_api").sync_playwright

ROOT = Path(__file__).resolve().parents[1]
CACHED = Path.home() / ".cache/ms-playwright/chromium-1208/chrome-linux64/chrome"
CHROMIUM = os.environ.get("THINKHOW_CHROMIUM", str(CACHED))
DESKTOP: dict[str, Any] = {"viewport": {"width": 1280, "height": 900}}
PHONE: dict[str, Any] = {
    "viewport": {"width": 390, "height": 844},
    "device_scale_factor": 2,
    "is_mobile": True,
    "has_touch": True,
}
SMALL_PHONE: dict[str, Any] = {**PHONE, "viewport": {"width": 360, "height": 740}}
TOPIC = "Кав'ярня біля дому"
REPLIES = [
    "Хочу відкрити маленьку кав'ярню біля дому.\nГроші є на пів року, досвіду — жодного.",
    "Боюся, що не буде людей уранці.\n\nА ще — що не впораюся сама з усім.",
]
LONG = "а" * 60
LUMINANCE = """(c) => { const [r, g, b] = c.match(/\\d+(\\.\\d+)?/g).slice(0, 3).map(Number).map((v) => {
  v /= 255; return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b; }"""

# The text of a turn as the eye reads it: its own text and the generated ::before of it and of its children.
LABELS = """(turn) => [turn, ...turn.querySelectorAll('*')].map((e) => {
  const c = getComputedStyle(e, '::before').content;
  return (c && c !== 'none' && c !== 'normal' ? c : '') + ' ';
}).join('') + turn.innerText"""


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="screens", help="the directory for the PNGs")
    out = Path(parser.parse_args().out)
    out.mkdir(parents=True, exist_ok=True)
    port, data = free_port(), tempfile.mkdtemp(prefix="thinkhow-design-")
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
            browser = p.chromium.launch(executable_path=CHROMIUM)
            walk(browser, base, out)
            browser.close()
        print(
            f"OK: dark theme, pending state, hidden buttons, line breaks, phone width; screenshots in {out}"
        )
    finally:
        server.terminate()
        server.wait(timeout=10)


def walk(browser: Any, base: str, out: Path) -> None:
    """Flow: conversation → screenshots in four contexts → pending → the ends of a request → width."""
    topic = conversation(new_page(browser, DESKTOP, "light"), base)
    backgrounds = {}
    for device, options in (("desktop", DESKTOP), ("phone", PHONE)):
        for scheme in ("light", "dark"):
            page = new_page(browser, options, scheme)
            backgrounds[(device, scheme)] = screens(page, base, topic, out, f"{device}-{scheme}")
            page.context.close()
    for device in ("desktop", "phone"):
        light, dark = backgrounds[(device, "light")], backgrounds[(device, "dark")]
        assert dark < 0.2 and dark < light, (device, light, dark)
    print("dark theme: body luminance", {k: round(v, 3) for k, v in backgrounds.items()})
    page = new_page(browser, PHONE, "light")
    pending(page, base + topic, out)
    request_ends(page, base + topic)
    page.context.close()
    widths(browser, base)


def new_page(browser: Any, options: dict[str, Any], scheme: str) -> Any:
    return browser.new_context(color_scheme=scheme, **options).new_page()


def conversation(page: Any, base: str) -> str:
    """Language → a topic → two replies answered by the local model; returns the topic's path."""
    page.goto(base + "/")
    if page.url.endswith("/language"):
        page.select_option('select[name="code"]', "uk-UA")
        page.click('form[action="/language"] button[type="submit"]')
        page.wait_for_url(base + "/")
    page.fill('input[name="title"]', TOPIC)
    page.click('form[action="/topics"] button[type="submit"]')
    page.wait_for_selector("#send")
    for no, text in enumerate(REPLIES, start=1):
        page.fill("textarea", text)
        page.click("#send")
        page.wait_for_function(
            f"document.querySelectorAll('article.turn').length === {2 * no}", timeout=15000
        )
    path = str(page.url)[len(base) :]
    print("conversation:", path, "—", page.locator("article.turn").count(), "turns")
    page.context.close()
    return path


def screens(page: Any, base: str, topic: str, out: Path, name: str) -> float:
    """«Мої теми» and the topic: screenshots and the fresh-page checks; returns the body luminance."""
    page.goto(base + "/")
    page.screenshot(path=str(out / f"home-{name}.png"), full_page=True)
    page.goto(base + topic)
    fresh_page_checks(page, name)
    page.screenshot(path=str(out / f"topic-{name}.png"), full_page=True)
    bg = page.evaluate("getComputedStyle(document.body).backgroundColor")
    luminance = float(page.evaluate(LUMINANCE, bg))
    print(f"{name}: screenshots taken; body background {bg}")
    return luminance


def fresh_page_checks(page: Any, name: str) -> None:
    """Seam 2–3 on a freshly loaded own topic page: hidden stays hidden, labels, line breaks."""
    for selector in ("#recognize", "#retry", "#pending"):
        assert not page.is_visible(selector), (name, selector)
    assert page.evaluate("document.getElementById('live').getBoundingClientRect().height") == 0, name
    model = page.locator("article.turn.model").first
    labels = model.evaluate(LABELS)
    assert labels.count("Фасилітатор") == 1, (name, labels)
    assert model.evaluate("e => e.getBoundingClientRect().height") < 200, (
        name,
        "blank lines in a saved answer",
    )
    assert model.locator(".text").evaluate("e => getComputedStyle(e).whiteSpace") == "pre-wrap", name
    user = page.locator("article.turn.user .text").first
    assert user.evaluate("e => getComputedStyle(e).whiteSpace") == "pre-wrap", name
    lines = user.evaluate(
        "e => e.getBoundingClientRect().height / parseFloat(getComputedStyle(e).lineHeight)"
    )
    assert lines > 1.5, (name, lines)  # two lines, measured with sub-pixel rounding
    probe = page.evaluate(
        """() => { const p = document.createElement('p'); p.className = 'turn model';
        document.getElementById('live').appendChild(p); const w = getComputedStyle(p).whiteSpace;
        const label = getComputedStyle(p, '::before').content; p.remove(); return [w, label]; }"""
    )
    assert probe == ["pre-wrap", '"Фасилітатор"'], (name, probe)


def pending(page: Any, url: str, out: Path) -> None:
    """Seam 2: «Фасилітатор відповідає…» while /reply is held, gone after `answered`."""
    page.goto(url)
    before = page.locator("article.turn").count()
    held: list[Any] = []
    page.route("**/reply", lambda r: held.append(r))
    page.fill("textarea", "Що, як перший місяць буде зовсім порожнім?")
    page.click("#send")
    wait(page, lambda: bool(held), "the held /reply")
    assert page.is_visible("#pending") and page.is_disabled("#send")
    page.screenshot(path=str(out / "topic-pending-phone-light.png"), full_page=True)
    print("pending: visible while /reply is held; screenshot taken")
    held[0].continue_()
    page.unroute("**/reply")
    page.wait_for_function(
        f"document.querySelectorAll('article.turn').length === {before + 2}", timeout=15000
    )
    assert not page.is_visible("#pending") and page.is_enabled("#send")
    print("pending: hidden after the answer; #send enabled;", before + 2, "turns")


def request_ends(page: Any, url: str) -> None:
    """Seam 2: an error fragment ends the pending state; a broken connection shows «Спробуйте ще раз»."""
    page.route(
        "**/reply",
        lambda r: r.fulfill(
            status=500,
            content_type="text/html; charset=utf-8",
            body='<p class="error">Перевірка: помилка сервера</p>',
        ),
    )
    page.fill("textarea", "Перевірка помилки")
    page.click("#send")
    page.wait_for_function("document.getElementById('error').textContent !== ''")
    assert not page.is_visible("#pending") and page.is_enabled("#send")
    print("500: pending hidden, #send enabled, error shown:", page.inner_text("#error"))
    page.unroute("**/reply")
    page.route("**/reply", lambda r: r.abort())
    page.click("#send")
    page.wait_for_selector("#retry", state="visible")
    assert not page.is_visible("#pending") and page.is_enabled("#send")
    print("network error: «Спробуйте ще раз» visible, pending hidden")
    page.unroute("**/reply")


def widths(browser: Any, base: str) -> None:
    """Seam 3: no horizontal scroll on a phone with a 60-letter word in a title and in a turn."""
    page = new_page(browser, DESKTOP, "light")
    page.goto(base + "/")
    page.fill('input[name="title"]', LONG)
    page.click('form[action="/topics"] button[type="submit"]')
    page.wait_for_selector("#send")
    page.fill("textarea", LONG)
    page.click("#send")
    page.wait_for_function("document.querySelectorAll('article.turn').length === 2", timeout=15000)
    long_topic = page.url
    page.context.close()
    for name, options in (("390", PHONE), ("360", SMALL_PHONE)):
        phone = new_page(browser, options, "light")
        for url in (base + "/", long_topic):
            phone.goto(url)
            # under mobile emulation innerWidth grows with wide content, so the device width is the measure
            scroll = phone.evaluate("document.documentElement.scrollWidth")
            assert scroll <= options["viewport"]["width"], (name, url, scroll)
        phone.context.close()
        print(f"width {name}px: no horizontal scroll on «Мої теми» and on the topic with a 60-letter word")


def wait(page: Any, ready: Callable[[], bool], what: str) -> None:
    """Poll through Playwright, so its events (the route handler) keep being dispatched."""
    for _ in range(150):
        if ready():
            return
        page.wait_for_timeout(100)
    raise AssertionError(f"timed out waiting for {what}")


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
