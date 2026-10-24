"""Screenshots and checks of task 203: the caption of the thinking model on a topic; real uvicorn + Chromium.

Run: `PYTHONPATH=src uv run --with playwright==1.64.1 python scripts/screenshots_current_model.py --out <dir>`
(Playwright is no project dependency). Chromium: `THINKHOW_CHROMIUM`, else the cached chromium-1208.
Seeds one topic through `workspace.reply` with a scripted facilitator (offer → «П'ять чому» to its end → the
weighted matrix at phase 2), then a fresh topic through the browser and the local model: «вільна розмова»
before the first reply, the card after it. Asserts by itself, leaves the PNGs in <dir>, ends with `OK:`.
"""

import argparse
import importlib
import os
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from screenshots_minimal_design import CHROMIUM, DESKTOP, PHONE, free_port, new_page, wait_for

from thinkhow.access import CurrentUser
from thinkhow.facilitation.types import Decision, FacilitatorUpdate, ReplyDelta, RoutingEvent
from thinkhow.platform.storage import LocalStorage
from thinkhow.workspace import TopicRef, create_topic, reply, set_language

sync_playwright = importlib.import_module("playwright.sync_api").sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OWNER = CurrentUser(id="local-owner", email="owner@localhost", is_owner=True)
T0 = datetime(2026, 10, 24, 12, 0, 0, tzinfo=UTC)
REV = {"rev": 2, "n": 18}
WHYS, MATRIX = "five-whys", "weighted-matrix"
# (the person's turn, the router's decisions before the reply, the reply, the phase after it, the end)
SCRIPT: list[tuple[str, list[dict[str, Any]], str, str | None, str | None]] = [
    (
        "Клієнти перестали повертатися, і я не можу вирішити, що робити: міняти меню чи переїжджати.",
        [{"kind": "offer"}],
        "Я зрозумів так: спершу хочеться знати, чому клієнти не повертаються, а потім уже обирати. "
        "Можна докопатися до причини, ставлячи «чому» крок за кроком, або одразу порівняти варіанти. "
        "Що ближче?",
        None,
        None,
    ),
    (
        "Давай спершу причину.",
        [{"kind": "choose", "card_id": WHYS}],
        "Добре. Сформулюймо проблему одним реченням: що саме сталося і відколи?",
        "phase_1_define_problem",
        None,
    ),
    (
        "З вересня повертається вдвічі менше людей, ніж улітку.",
        [],
        "Чому, на вашу думку, вони не повертаються? Назвіть кілька пояснень.",
        "phase_2_chain_and_branches",
        None,
    ),
    (
        "Поруч відкрилася мережева кав'ярня, а наші ціни не змінювалися два роки.",
        [],
        "Отже, головна гілка — конкурент з нижчою ціною. Тепер варто вирішити, що з цим робити.",
        "phase_3_reverse_check_and_change",
        "done",
    ),
    (
        "Так, тепер обираю між трьома варіантами: знизити ціни, змінити меню або переїхати.",
        [{"kind": "choose", "card_id": MATRIX}],
        "Розгляньмо три варіанти. Що для вас найважливіше, коли ви їх порівнюєте?",
        "phase_1_frame_options",
        None,
    ),
    (
        "Гроші, час і щоб не втратити постійних гостей.",
        [],
        "Гроші, час і постійні гості — три критерії. Чи є ще щось, без чого рішення не буде вашим?",
        "phase_2_criteria",
        None,
    ),
]


def decision(turn: int, kind: str, card_id: str | None = None, end: str | None = None) -> Decision:
    fields = {"turn": turn, "rev": REV, "kind": kind, "profile": None, "candidates": []}
    return Decision.model_validate({**fields, "card_id": card_id, "end": end, "why": "сценарій знімка"})


def seed(data: Path) -> TopicRef:
    """The topic of the screenshot, written by the product's own `workspace.reply`."""
    store = LocalStorage(data)
    set_language(store, OWNER, "uk-UA")
    ref = TopicRef(OWNER.id, create_topic(store, OWNER, "Кав'ярня: клієнти не повертаються", T0))
    card: str | None = None
    for i, (text, before, answer, phase, end) in enumerate(SCRIPT):
        turn = 2 * i + 1
        events: list[Any] = [RoutingEvent(decision(turn, **d)) for d in before]
        card = next((d["card_id"] for d in before if d["kind"] == "choose"), card)
        if end is not None:
            events.append(RoutingEvent(decision(turn, "end", card, end)))
        update = FacilitatorUpdate(reply=answer, current_phase_id=phase, phase_exit_met=False, map_updates=[])
        events += [ReplyDelta(answer), update]

        def facilitate(ctx: Any, items: list[Any] = events) -> Iterator[Any]:
            return iter(items)

        list(reply(store, facilitate, OWNER, ref, text, T0))
    return ref


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="screens", help="the directory for the PNGs")
    out = Path(parser.parse_args().out)
    out.mkdir(parents=True, exist_ok=True)
    port, data = free_port(), Path(tempfile.mkdtemp(prefix="thinkhow-model-"))
    ref = seed(data)
    env = {
        **os.environ,
        "PYTHONPATH": str(ROOT / "src"),
        "THINKHOW_LOCAL": "true",
        "THINKHOW_LOCAL_DIR": str(data),
    }
    command = [sys.executable, "-m", "uvicorn", "thinkhow.web.app:app", "--port", str(port)]
    server = subprocess.Popen(command, cwd=ROOT, env=env)
    base = f"http://localhost:{port}"
    try:
        wait_for(base + "/language")
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=CHROMIUM)
            seeded(browser, f"{base}/topics/{ref.uid}/{ref.topic_id}", out)
            live(browser, base, out)
            browser.close()
        print(f"OK: caption and marks on the seeded topic, free → the card live; screenshots in {out}")
    finally:
        server.terminate()
        server.wait(timeout=10)


def seeded(browser: Any, url: str, out: Path) -> None:
    for device, options in (("desktop", DESKTOP), ("phone", PHONE)):
        page = new_page(browser, options, "light")
        page.goto(url)
        method = page.locator("aside.method").inner_text()
        assert method == "Модель мислення: Зважене порівняння варіантів за власними цінностями · 2 з 4", (
            method
        )
        assert page.locator("aside.method").is_visible()
        found = page.locator(".method-mark").all_inner_texts()
        assert found == [
            "Далі веде модель мислення «П'ять «чому» з розгалуженням»",
            "«П'ять «чому» з розгалуженням» пройдено · далі вільна розмова",
            "Далі веде модель мислення «Зважене порівняння варіантів за власними цінностями»",
        ], found
        for text in page.locator("article.turn.model .text").all_inner_texts():
            assert "модель мислення" not in text.lower(), text
        print(device, "caption:", method, "| marks:", len(found))
        page.screenshot(path=str(out / f"topic-model-{device}.png"), full_page=device == "phone")
        page.context.close()


def live(browser: Any, base: str, out: Path) -> None:
    """A new topic in the browser: free before the first reply; the local router chooses Pre-mortem."""
    page = new_page(browser, DESKTOP, "light")
    page.goto(base + "/")
    page.fill('input[name="title"]', "Нова тема")
    page.click('form[action="/topics"] button[type="submit"]')
    page.wait_for_selector("#send")
    before = page.locator("aside.method").inner_text()
    assert before == "Модель мислення: вільна розмова", before
    page.fill("textarea", "Хочу відкрити кав'ярню.")
    page.click("#send")
    page.wait_for_function("document.querySelectorAll('article.turn').length === 2", timeout=15000)
    after = page.locator("aside.method").inner_text()
    assert after.startswith("Модель мислення: Pre-mortem") and after.endswith("· 1 з 4"), after
    print("live:", before, "→", after)
    page.screenshot(path=str(out / "topic-model-live.png"))
    page.context.close()


if __name__ == "__main__":
    main()
