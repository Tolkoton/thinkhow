"""Block tests of document-upload (slice tester, mode `block`): one per acceptance criterion AC1–AC7.

The feature `.engine/architecture/feature/document-upload.md` has one slice and one block, so «Inter-slice
contracts» names no connection between blocks («Немає (один slice)») and there is no connection test; the
feature is closed with S1, so every acceptance criterion gets one test. Written from the feature artifact and
the public signatures, not the bodies.

Every person's action goes the way a person does it — through the web app (`POST …/document`,
`POST …/reply`, `GET` of the page) with a clock the test moves, a real `LocalStorage`, the real text
extraction and a recording facilitator double. AC5's Playwright part is the smoke script itself; AC6 is
read from the artifact of the live check (`scripts/live_document_upload.py`); AC7 from the architecture
map and the image's build inputs.
The sealed helpers of the slice (`du_fakes`) are reused as they are.
"""

from __future__ import annotations

import html
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
_SLICE = str(HERE.parent / "document_upload")
if _SLICE not in sys.path:
    sys.path.insert(0, _SLICE)


from du_fakes import (  # noqa: E402
    ALICE,
    BOB,
    DAY,
    IAP,
    LOCALES,
    MAX,
    RESUME_PDF_TEXT,
    ROOT,
    T0,
    Facil,
    M,
    Tags,
    document_url,
    file_bytes,
    new_topic,
    page_url,
    sse_events,
    topic_files,
    turns,
)
from fastapi.testclient import TestClient  # noqa: E402

from thinkhow.access import CurrentUser  # noqa: E402
from thinkhow.facilitation.types import Turn, document_turn  # noqa: E402
from thinkhow.platform.config import load_settings  # noqa: E402
from thinkhow.platform.documents import extract  # noqa: E402
from thinkhow.platform.identity import IapIdentity  # noqa: E402
from thinkhow.platform.speech import ScriptedSpeech  # noqa: E402
from thinkhow.platform.storage import LocalStorage  # noqa: E402
from thinkhow.web.server import Deps, create_app  # noqa: E402
from thinkhow.workspace import TopicRef, set_language  # noqa: E402

OWNER = CurrentUser(id="owner-9", email="owner@example.com", is_owner=True)
TOKENS = {
    "tok-alice": {"sub": "accounts.google.com:alice-1", "email": "alice@example.com"},
    "tok-bob": {"sub": "accounts.google.com:bob-2", "email": "bob@example.com"},
    "tok-owner": {"sub": "accounts.google.com:owner-9", "email": "owner@example.com"},
}
AS_ALICE = {IAP: "tok-alice"}
AS_BOB = {IAP: "tok-bob"}
AS_OWNER = {IAP: "tok-owner"}
PAPERCLIP = "📎 "
ARTIFACTS = ROOT / ".engine" / "artifacts" / "document-upload"
SMOKE = ROOT / "scripts" / "smoke_test_document_upload.py"


class Clock:
    def __init__(self, at: datetime) -> None:
        self.at = at

    def __call__(self) -> datetime:
        return self.at


def app(
    tmp_path: Path, storage: LocalStorage, facil: Facil, clock: Clock, alice_lang: str = "uk-UA"
) -> TestClient:
    set_language(storage, ALICE, alice_lang)
    set_language(storage, BOB, "uk-UA")
    set_language(storage, OWNER, "uk-UA")
    settings = load_settings(
        {
            "THINKHOW_LOCAL": "true",
            "THINKHOW_LOCAL_DIR": str(tmp_path),
            "THINKHOW_OWNER_EMAIL": "owner@example.com",
        }
    )
    deps = Deps(
        storage=storage,
        identity=IapIdentity("aud-test", lambda token, audience: TOKENS[token]),
        settings=settings,
        facilitate=facil,
        now=clock,
        speech=ScriptedSpeech(""),
    )
    return TestClient(create_app(deps), raise_server_exceptions=False, follow_redirects=False)


def post_file(
    client: TestClient, ref: TopicRef, name: str, data: bytes, headers: dict[str, str] = AS_ALICE
) -> Any:
    return client.post(
        document_url(ref), files={"file": (name, data, "application/octet-stream")}, headers=headers
    )


def say(client: TestClient, ref: TopicRef, text: str, headers: dict[str, str] = AS_ALICE) -> Any:
    return client.post(f"/topics/{ref.uid}/{ref.topic_id}/reply", data={"text": text}, headers=headers)


def event_names(body: str) -> list[str]:
    return [name for name, _ in sse_events(body)]


def words(catalog: str) -> dict[str, str]:
    data: dict[str, str] = json.loads((LOCALES / f"{catalog}.json").read_text(encoding="utf-8"))
    return data


def visible(body: str) -> str:
    return html.unescape(body)


# --- AC1 --------------------------------------------------------------------------------------------------


def test_ac1_the_paperclip_icon_button_sits_by_the_mic_and_send_and_takes_pdf_docx_txt_md(
    tmp_path: Path,
) -> None:
    storage = LocalStorage(tmp_path / "data")
    ref = new_topic(storage)
    client = app(tmp_path, storage, Facil(), Clock(T0))
    r = client.get(page_url(ref), headers=AS_ALICE)
    assert r.status_code == 200, r.text
    page = Tags(r.text)
    tag, attrs = page.by_id("attach")
    assert tag == "button"
    label = attrs.get("aria-label")
    assert label and label == words("uk")["upload_document"], label
    assert page.texts.get("attach", "").strip() == "", "the paperclip is an icon without words"
    # «поряд із мікрофоном і „Надіслати“»: between the two, as the slice placed it
    assert page.index_of("mic") < page.index_of("attach") < page.index_of("send")
    tag, attrs = page.by_id("document")
    assert tag == "input" and attrs.get("type") == "file"
    accepted = {a.strip().lower() for a in (attrs.get("accept") or "").split(",")}
    assert {".pdf", ".docx", ".txt", ".md"} <= accepted, accepted
    # each of the four formats, sent through the button's route, becomes a turn with its name
    clock = Clock(T0)
    client = app(tmp_path, storage, Facil(), clock)
    sent = [
        ("resume.pdf", file_bytes("resume.pdf")),
        ("resume.docx", file_bytes("resume.docx")),
        ("cv.txt", "Резюме: Олена, продакт-менеджерка.".encode()),
        ("cv.md", "# Резюме\n\nОлена, продакт-менеджерка.".encode()),
    ]
    for name, data in sent:
        clock.at += M
        r = post_file(client, ref, name, data)
        assert r.status_code == 200, (name, r.status_code, r.text)
        assert event_names(r.text)[-1] == "answered", (name, r.text)
    user_turns = [t.text for t in turns(storage, ref, clock.at + M) if t.role == "user"]
    assert user_turns == [PAPERCLIP + n for n, _ in sent], user_turns


# --- AC2 --------------------------------------------------------------------------------------------------


def test_ac2_the_document_belongs_to_its_topic_read_by_its_person_and_the_owner_kept_after_a_break(
    tmp_path: Path,
) -> None:
    root = tmp_path / "data"
    storage = LocalStorage(root)
    ref = new_topic(storage)
    other = new_topic(storage, T0 - 5 * M)
    facil = Facil(["Бачу ваш досвід у fintech. Що для вас зараз головне?"])
    clock = Clock(T0)
    client = app(tmp_path, storage, facil, clock)

    # someone else cannot give Alice's topic a document, the owner neither (only its person writes)
    for headers in (AS_BOB, AS_OWNER):
        before = topic_files(root, ref)
        r = post_file(client, ref, "resume.pdf", file_bytes("resume.pdf"), headers)
        assert r.status_code == 404, (headers, r.status_code, r.text)
        assert topic_files(root, ref) == before
    assert facil.contexts == []

    r = post_file(client, ref, "resume.pdf", file_bytes("resume.pdf"))
    assert r.status_code == 200, r.text
    # stored with the topic's conversation under users/<uid>/<topic>/
    stored = topic_files(root, ref)
    assert "documents.json" in stored and "conversation.md" in stored, sorted(stored)
    assert "Monobank" in stored["documents.json"].decode("utf-8")
    assert "Monobank" not in stored["conversation.md"].decode("utf-8")
    assert "📎 resume.pdf" in stored["conversation.md"].decode("utf-8")
    assert "documents.json" not in topic_files(root, other)

    # its person and the owner see it; another person does not
    assert "📎 resume.pdf" in visible(client.get(page_url(ref), headers=AS_ALICE).text)
    owner_page = client.get(page_url(ref), headers=AS_OWNER)
    assert owner_page.status_code == 200 and "📎 resume.pdf" in visible(owner_page.text)
    bob_page = client.get(page_url(ref), headers=AS_BOB)
    assert bob_page.status_code == 404 and "📎" not in visible(bob_page.text)

    # after a break (a new session, a new request) the model still has it, nobody uploads it again
    clock.at = T0 + DAY
    later = Facil(["Тоді почнімо з досвіду. Що далі?"])
    client = app(tmp_path, storage, later, clock)
    r = say(client, ref, "Повертаюся до теми. Що мені з цим робити?")
    assert r.status_code == 200 and event_names(r.text)[-1] == "answered", r.text
    (ctx,) = later.contexts
    assert ctx.text == "Повертаюся до теми. Що мені з цим робити?"
    framed = [t for t in ctx.history if t.role == "user" and RESUME_PDF_TEXT in t.text]
    assert framed == [Turn("user", document_turn("resume.pdf", RESUME_PDF_TEXT))], ctx.history
    # one document belongs to one topic: Alice's other topic does not see it
    elsewhere = Facil()
    client = app(tmp_path, storage, elsewhere, clock)
    assert event_names(say(client, other, "Інша тема.").text)[-1] == "answered"
    (octx,) = elsewhere.contexts
    assert all("Monobank" not in t.text for t in octx.history) and "Monobank" not in octx.text


# --- AC3 --------------------------------------------------------------------------------------------------


def test_ac3_the_document_is_the_persons_named_turn_answered_at_once_from_its_text_and_remembered(
    tmp_path: Path,
) -> None:
    storage = LocalStorage(tmp_path / "data")
    ref = new_topic(storage)
    first = "Бачу в резюме 7 років у fintech і кешбек у Monobank. Що ви хочете змінити?"
    facil = Facil([first, "Зрозуміло. Що з цього для вас найважливіше?"])
    clock = Clock(T0)
    client = app(tmp_path, storage, facil, clock)

    r = post_file(client, ref, "resume.pdf", file_bytes("resume.pdf"))
    assert r.status_code == 200, r.text
    names = event_names(r.text)
    assert names[0] == "saved" and "delta" in names and names[-1] == "answered", names
    # the model answered the document itself: its text in a frame naming the file, not the bare name
    (ctx,) = facil.contexts
    assert ctx.text != "📎 resume.pdf"
    assert "resume.pdf" in ctx.text and RESUME_PDF_TEXT in ctx.text
    assert ctx.text == document_turn("resume.pdf", RESUME_PDF_TEXT)
    # the person's turn shows the file's name; the answer follows it
    clock.at += M
    page = visible(client.get(page_url(ref), headers=AS_ALICE).text)
    assert "📎 resume.pdf" in page and first in page
    assert [(t.role, t.text) for t in turns(storage, ref, clock.at)] == [
        ("user", "📎 resume.pdf"),
        ("model", first),
    ]
    # further in the topic the model remembers the document
    clock.at += M
    r = say(client, ref, "Хочу перейти в більшу компанію.")
    assert r.status_code == 200, r.text
    later = facil.contexts[1]
    assert later.history[0] == Turn("user", document_turn("resume.pdf", RESUME_PDF_TEXT))
    assert later.history[1] == Turn("model", first)
    assert later.text == "Хочу перейти в більшу компанію."


# --- AC4 --------------------------------------------------------------------------------------------------


def test_ac4_an_unreadable_or_too_large_file_says_so_in_the_persons_language_and_the_talk_goes_on(
    tmp_path: Path,
) -> None:
    root = tmp_path / "data"
    storage = LocalStorage(root)
    ref = new_topic(storage)
    facil = Facil(["Добре. Що далі?"])
    clock = Clock(T0)
    client = app(tmp_path, storage, facil, clock, alice_lang="de-DE")
    de = words("de")
    assert de["err_document_unreadable"] != words("uk")["err_document_unreadable"]

    unreadable = [
        ("scan.pdf", file_bytes("scan.pdf")),  # a scan without text
        ("broken.pdf", b"%PDF-1.4\n\x00\x01 not a pdf at all"),  # damaged
        ("encrypted.pdf", file_bytes("encrypted.pdf")),  # needs a password
        ("table.xlsx", file_bytes("resume.docx")),  # not a format of the feature
        ("broken.docx", b"PK\x03\x04 not a zip"),
    ]
    for name, data in unreadable:
        before = topic_files(root, ref)
        clock.at += M
        r = post_file(client, ref, name, data)
        assert r.status_code == 422, (name, r.status_code, r.text)
        assert de["err_document_unreadable"] in visible(r.text), (name, r.text)
        assert topic_files(root, ref) == before, name

    # too large for the model window: the topic's documents together over 200 000 characters
    clock.at += M
    big = ("я" * MAX).encode("utf-8")
    assert post_file(client, ref, "big.txt", big).status_code == 200  # exactly the limit is taken (P5)
    before = topic_files(root, ref)
    clock.at += M
    r = post_file(client, ref, "one-more.txt", "ж".encode())
    assert r.status_code == 413, (r.status_code, r.text)
    assert de["err_document_too_large"] in visible(r.text), r.text
    assert topic_files(root, ref) == before

    # the conversation is not broken: the page opens and the next message is answered
    clock.at += M
    assert client.get(page_url(ref), headers=AS_ALICE).status_code == 200
    r = say(client, ref, "Gut, dann schreibe ich einfach.")
    assert r.status_code == 200 and event_names(r.text)[-1] == "answered", r.text
    user_turns = [t.text for t in turns(storage, ref, clock.at + M) if t.role == "user"]
    assert user_turns == ["📎 big.txt", "Gut, dann schreibe ich einfach."], user_turns


# --- AC5 --------------------------------------------------------------------------------------------------


def test_ac5_playwright_in_local_mode_shows_the_button_takes_pdf_and_docx_and_keeps_them_after_reload(
    tmp_path: Path,
) -> None:
    # the Playwright part: the feature's smoke, real uvicorn in local mode and real Chromium
    uv = shutil.which("uv")
    assert uv, "uv is needed to run the smoke"
    proc = subprocess.run(
        [uv, "run", "--project", str(ROOT), "python", str(SMOKE)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=480,
    )
    out = proc.stdout + proc.stderr
    assert proc.returncode == 0, out[-4000:]
    assert any(line.startswith("OK:") for line in proc.stdout.splitlines()), out[-4000:]
    shots = [p for p in tmp_path.rglob("*.png") if p.stat().st_size > 0]
    assert shots, "no screenshot of the topic page"
    # the same path in the app: PDF and DOCX → named turns with answers, and after reload still in the topic
    storage = LocalStorage(tmp_path / "data")
    ref = new_topic(storage)
    facil = Facil(["Бачу PDF. Що далі?", "Бачу DOCX. Що далі?"])
    clock = Clock(T0)
    client = app(tmp_path, storage, facil, clock)
    for name in ("resume.pdf", "resume.docx"):
        clock.at += M
        r = post_file(client, ref, name, file_bytes(name))
        assert r.status_code == 200 and event_names(r.text)[-1] == "answered", (name, r.text)
    clock.at += M
    reloaded = visible(client.get(page_url(ref), headers=AS_ALICE).text)
    for shown in ("📎 resume.pdf", "Бачу PDF. Що далі?", "📎 resume.docx", "Бачу DOCX. Що далі?"):
        assert shown in reloaded, shown
    texts = topic_files(tmp_path / "data", ref)["documents.json"].decode("utf-8")
    assert "Monobank" in texts and json.loads(texts)


# --- AC6 --------------------------------------------------------------------------------------------------


def _latest_live() -> tuple[str, Path]:
    found = sorted(ARTIFACTS.glob("live-*.md"))
    assert found, f"no live check in {ARTIFACTS}"
    md = found[-1]
    return md.read_text(encoding="utf-8"), md.with_suffix(".pdf")


def test_ac6_live_on_the_real_model_the_first_answer_rests_on_the_resume_and_ends_with_one_question() -> None:
    text, pdf = _latest_live()
    assert "gemini-4-argon" in text
    assert re.search(r"робот", text, re.IGNORECASE), "the topic is about a job search"
    # an invented résumé in PDF, kept beside the record
    assert pdf.exists() and pdf.read_bytes().startswith(b"%PDF"), pdf
    resume = extract(pdf.name, pdf.read_bytes())
    # the first answer: the section of the first document turn
    sections = re.split(r"^## ", text, flags=re.MULTILINE)
    first = next((s for s in sections[1:] if "📎" in s.split("\n", 1)[0]), None)
    assert first is not None, "no section for the document turn"
    answer = first.split("\n", 1)[1].strip()
    assert answer, "the first answer is empty"
    # concrete from the résumé (experience, skills), not general words: at least three of its own
    # distinctive tokens — numbers, names, tools — in the answer
    tokens = {
        w
        for w in re.findall(r"[\w+#%−-]+", resume)
        if (any(c.isdigit() for c in w) or w[:1].isupper() or w.isupper()) and len(w) >= 3
    }
    hits = {w for w in tokens if w in answer}
    assert len(hits) >= 3, (sorted(hits), answer)
    # ends with one question
    assert answer.rstrip().endswith("?"), answer
    assert answer.count("?") == 1, answer


# --- AC7 --------------------------------------------------------------------------------------------------


def test_ac7_the_architecture_names_the_module_and_the_file_and_the_image_gets_pypdf_from_the_lock() -> None:
    amap = (ROOT / ".engine" / "architecture" / "architecture-map.md").read_text(encoding="utf-8")
    assert "platform.documents" in amap
    assert "documents.json" in amap
    # deployment needs nothing new: the image installs the locked dependencies, pypdf among them
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert re.search(r"uv sync[^\n]*--frozen", dockerfile), dockerfile
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert re.search(r'"pypdf[>=~ ]', pyproject), "pypdf is not a dependency"
    lock = (ROOT / "uv.lock").read_text(encoding="utf-8")
    assert 'name = "pypdf"' in lock
