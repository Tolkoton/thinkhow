"""The live check of task 311 (feature document-upload, AC6): a new topic about a job search and an invented
résumé in PDF, through the product's `workspace.add_document` on the real model (`gemini-4-argon`, Vertex
`eu`, search on).

Run: `uv run python scripts/live_document_upload.py --out .engine/artifacts/document-upload`.
The résumé is invented (not the owner's): Chromium prints it to PDF, the product extracts it, the facilitator
answers.
Then one ordinary reply, to see the document still in the topic. Writes `live-<stamp>.md` with both answers.
"""

import argparse
import functools
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

from thinkhow import knowledge, workspace
from thinkhow.access import CurrentUser
from thinkhow.facilitation import respond
from thinkhow.platform.config import load_settings
from thinkhow.platform.llm import make_llm
from thinkhow.platform.storage import LocalStorage

ROOT = Path(__file__).resolve().parents[1]
PERSON = CurrentUser(id="live-311", email="live-311@example.com", is_owner=False)
TITLE = "Шукаю нову роботу: куди рухатись після 6 років у логістиці"
RESUME = """<html><body style="font-family: sans-serif">
<h1>Марта Гнатюк</h1><p>Львів · керівниця відділу планування поставок</p>
<h2>Досвід</h2><ul>
<li>2021–2025 — «Галтранс Логістик», керівниця планування поставок: команда з 9 людей, перевела планування
з Excel на Power BI і скоротила простої складу на 18 %.</li>
<li>2019–2021 — «Епіцентр К», аналітикиня запасів: прогноз попиту для 40 магазинів, Python (pandas).</li>
<li>2018–2019 — стажування в DHL Supply Chain, Варшава.</li></ul>
<h2>Навички</h2><p>SQL, Power BI, Python (pandas), SAP MM; англійська B2, польська B1.</p>
<h2>Освіта</h2><p>Львівська політехніка, магістр з логістики (2018). Курс Google Data Analytics (2024).</p>
</body></html>"""
FOLLOW_UP = "Мені цікаво, чи варто йти в аналітику даних, чи лишатися в логістиці."


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=".engine/artifacts/document-upload")
    out = Path(parser.parse_args().out)
    out.mkdir(parents=True, exist_ok=True)
    storage = LocalStorage(Path(tempfile.mkdtemp(prefix="thinkhow-live-311-")))
    local = load_settings({**os.environ, "THINKHOW_LOCAL": "true", "THINKHOW_LOCAL_DIR": tempfile.mkdtemp()})
    settings = local.model_copy(update={"local": False})
    knowledge.seed(storage, ROOT / "cards")
    current = knowledge.current(storage)
    facilitate = functools.partial(
        respond, knowledge=current, llm=make_llm(settings, lambda *_: "", search=True)
    )
    workspace.ensure_profile(storage, PERSON)
    workspace.set_language(storage, PERSON, "uk-UA")
    now = datetime.now(UTC)
    topic = workspace.TopicRef(PERSON.id, workspace.create_topic(storage, PERSON, TITLE, now))
    pdf = print_pdf(RESUME)
    first = answer(
        workspace.add_document(storage, facilitate, PERSON, topic, "Marta_Hnatiuk_CV.pdf", pdf, now)
    )
    second = answer(workspace.reply(storage, facilitate, PERSON, topic, FOLLOW_UP, datetime.now(UTC)))
    stamp = now.strftime("%Y-%m-%dT%H%M%SZ")
    (out / f"live-{stamp}.pdf").write_bytes(pdf)
    report = out / f"live-{stamp}.md"
    report.write_text(render(stamp, first, second), encoding="utf-8")
    print(f"OK: {report}")


def print_pdf(html: str) -> bytes:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(html)
        data: bytes = page.pdf()
        browser.close()
    return data


def answer(events: object) -> str:
    """The answer's text from the stream; a failure is the answer (the report says so)."""
    text = ""
    for event in events:  # type: ignore[attr-defined]
        if isinstance(event, workspace.Delta):
            text += event.text
        if isinstance(event, workspace.Failed):
            return f"(FAILED: {event.reason})"
    return text


def render(stamp: str, first: str, second: str) -> str:
    return (
        f"# Жива перевірка задачі 311 — {stamp}\n\n"
        f"Модель: `gemini-4-argon`, Vertex `eu`, з пошуком; `workspace.add_document`. Тема: «{TITLE}».\n"
        f"Резюме вигадане (Марта Гнатюк), PDF надруковано Chromium: `live-{stamp}.pdf`.\n\n"
        "## Репліка 1 — `📎 Marta_Hnatiuk_CV.pdf`, відповідь фасилітатора\n\n"
        f"{first}\n\n"
        f"## Репліка 3 — «{FOLLOW_UP}», відповідь\n\n"
        f"{second}\n"
    )


if __name__ == "__main__":
    main()
