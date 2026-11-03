"""Helpers for the document-upload contract tests (slice tester). Built from the contract
`.engine/slices/document-upload.md` and the public signatures, not the code.

- FILES: the spike's real files (Seam 1): `resume.pdf` (Chromium-printed, Cyrillic), `scan.pdf`
  (image only), `encrypted.pdf` (needs a password), `resume.docx`.
  RESUME_PDF_TEXT / RESUME_DOCX_TEXT are their texts written by hand from
  the spike's output (`.engine/artifacts/spikes/document-upload-2026-11-03/spike.out`).
- docx(...): a DOCX built by hand with zipfile (paragraphs of runs in `word/document.xml`).
- Facil: a recording `Facilitate` double; `answers` is consumed one per call (None → the model fails).
- Rec / Q: the injected `Recognize` and `Question` of S6.
- PathFailStorage: a LocalStorage whose writes to paths ending in `fail_suffix` raise `StorageBroke`
  (the pattern of `ArmedStorage`, made selective by path — Seam 2b).
- topic_files: a snapshot of every stored file of a topic (Seam 3).
- entries: the entries of `documents.json`, read whether the file is `{"entries": [...]}` (research.json's
  convention) or a bare list (Q3: the tests do not depend on the wrapper).
- too_large(exc): the refusal is recognised by the class name `DocumentTooLarge`
  (Q8: the contract names the error, not its module).
"""

from __future__ import annotations

import io
import json
import zipfile
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from thinkhow.access import CurrentUser
from thinkhow.facilitation.types import (
    FacilitationContext,
    FacilitatorUpdate,
    MapUpdate,
    ReplyDelta,
    StepOutcome,
)
from thinkhow.platform.config import load_settings
from thinkhow.platform.identity import IapIdentity
from thinkhow.platform.speech import ScriptedSpeech
from thinkhow.platform.storage import Bucket, LocalStorage
from thinkhow.web.server import Deps, create_app
from thinkhow.workspace import (
    NumberedTurn,
    ReplyEvent,
    TopicRef,
    create_topic,
    open_topic,
    reply,
    retry,
    set_language,
)

HERE = Path(__file__).resolve().parent
FILES = HERE / "files"
ROOT = Path(__file__).resolve().parents[3]
LOCALES = ROOT / "src" / "thinkhow" / "web" / "locales"

RESUME_PDF_TEXT = (
    "Олена Коваль\n"
    "Продакт-менеджерка, 7 років у fintech.\n"
    "2019–2024 — Monobank: запустила кешбек-сервіс, 1,2 млн користувачів\n"
    "SQL, Amplitude, A/B-тести\n"
    "English: Product manager, Kyiv."
)
RESUME_DOCX_TEXT = "Олена Коваль\nДосвід: Monobank"

MAX = 200_000  # MAX_DOCUMENT_CHARS, written by hand from the contract

T0 = datetime(2026, 11, 3, 9, 0, 0, tzinfo=UTC)
S1 = timedelta(seconds=1)
M = timedelta(minutes=1)
H = timedelta(hours=1)
DAY = timedelta(hours=25)  # more than the 24 h of silence

ALICE = CurrentUser(id="alice-1", email="alice@example.com", is_owner=False)
BOB = CurrentUser(id="bob-2", email="bob@example.com", is_owner=False)

IAP = "x-goog-iap-jwt-assertion"
TOKENS: dict[str, dict[str, str]] = {
    "tok-alice": {"sub": "accounts.google.com:alice-1", "email": "alice@example.com"},
    "tok-bob": {"sub": "accounts.google.com:bob-2", "email": "bob@example.com"},
}
H_ALICE = {IAP: "tok-alice"}
H_BOB = {IAP: "tok-bob"}

STEP = "Поговорити з трьома клієнтами"
NEW_KEYS = ("upload_document", "err_document_unreadable", "err_document_too_large", "js_document_too_large")


def file_bytes(name: str) -> bytes:
    return (FILES / name).read_bytes()


W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
CONTENT_TYPES = (
    '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/word/document.xml" '
    'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>'
)


def document_xml(paragraphs: Sequence[Sequence[str]], doctype: bool = False) -> str:
    body = "".join(
        "<w:p>" + "".join(f'<w:r><w:t xml:space="preserve">{run}</w:t></w:r>' for run in runs) + "</w:p>"
        for runs in paragraphs
    )
    head = '<?xml version="1.0" encoding="UTF-8"?>'
    if doctype:
        head += '<!DOCTYPE w:document [<!ENTITY x "x">]>'
    return f'{head}<w:document xmlns:w="{W}"><w:body>{body}</w:body></w:document>'


def zip_of(parts: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, text in parts.items():
            z.writestr(name, text)
    return buf.getvalue()


def docx(paragraphs: Sequence[Sequence[str]], doctype: bool = False) -> bytes:
    return zip_of(
        {"[Content_Types].xml": CONTENT_TYPES, "word/document.xml": document_xml(paragraphs, doctype)}
    )


def reason_of(exc: BaseException) -> Any:
    """`Unreadable(reason)`: the reason as an attribute, else the first argument (Q2: either)."""
    return getattr(exc, "reason", exc.args[0] if exc.args else None)


def too_large(exc: BaseException) -> bool:
    return any(k.__name__ == "DocumentTooLarge" for k in type(exc).__mro__)


# --- the facilitator ---------------------------------------------------------------------------------


class Down(Exception):
    """The facilitator's model failed."""


@dataclass
class Facil:
    """Answers in order; None → the model fails (the turn stays unanswered); past the list: a default."""

    answers: list[str | None] = field(default_factory=list)
    updates: Sequence[MapUpdate] = ()
    contexts: list[FacilitationContext] = field(default_factory=list)

    def __call__(self, context: FacilitationContext) -> Iterator[Any]:
        self.contexts.append(context)
        answer = self.answers.pop(0) if self.answers else "Добре. Що далі?"
        return self._run(answer)

    def _run(self, answer: str | None) -> Iterator[Any]:
        if answer is None:
            raise Down("down")
        yield ReplyDelta(text=answer)
        yield FacilitatorUpdate(
            reply=answer, current_phase_id=None, phase_exit_met=False, map_updates=list(self.updates)
        )


def Q(arg: str) -> str:
    """The injected `Question`."""
    return "Минулого разу ви обрали крок «{step}» (" + arg + "). Як він вийшов?"


@dataclass
class Rec:
    result: StepOutcome | None = None
    calls: list[tuple[str, str, str]] = field(default_factory=list)

    def __call__(self, step: str, question: str, text: str) -> StepOutcome | None:
        self.calls.append((step, question, text))
        return self.result


def worked() -> StepOutcome:
    return StepOutcome.model_validate(
        {"answered": True, "outcome": "worked", "clearer": "yes", "said": "двоє готові платити"}
    )


# --- the storage ---------------------------------------------------------------------------------------


class StorageBroke(Exception):
    """A write that failed."""


class PathFailStorage(LocalStorage):
    """Writes to a path ending in `fail_suffix` raise `StorageBroke`; every other write goes through."""

    def __init__(self, root: Path) -> None:
        super().__init__(root)
        self.fail_suffix: str | None = None

    def _check(self, path: str) -> None:
        if self.fail_suffix is not None and path.endswith(self.fail_suffix):
            raise StorageBroke(f"write of {path} failed")

    def write(self, bucket: Bucket, path: str, data: bytes, content_type: str) -> None:
        self._check(path)
        super().write(bucket, path, data, content_type)

    def create_if_absent(self, bucket: Bucket, path: str, data: bytes, content_type: str) -> bool:
        self._check(path)
        return super().create_if_absent(bucket, path, data, content_type)


def topic_dir(root: Path, ref: TopicRef) -> Path:
    return root / "users" / ref.uid / ref.topic_id


def topic_files(root: Path, ref: TopicRef) -> dict[str, bytes]:
    base = topic_dir(root, ref)
    if not base.exists():
        return {}
    return {str(p.relative_to(base)): p.read_bytes() for p in sorted(base.rglob("*")) if p.is_file()}


def entries(storage: LocalStorage, ref: TopicRef) -> list[dict[str, Any]]:
    raw = storage.read("users", f"{ref.uid}/{ref.topic_id}/documents.json")
    if raw is None:
        return []
    data = json.loads(raw)
    found = data["entries"] if isinstance(data, dict) else data
    assert isinstance(found, list), data
    return [dict(e) for e in found]


def conversation_md(storage: LocalStorage, ref: TopicRef) -> str:
    raw = storage.read("users", f"{ref.uid}/{ref.topic_id}/conversation.md")
    assert raw is not None
    return raw.decode("utf-8")


# --- the topic -----------------------------------------------------------------------------------------


def new_topic(storage: LocalStorage, at: datetime = T0 - 10 * M, user: CurrentUser = ALICE) -> TopicRef:
    return TopicRef(user.id, create_topic(storage, user, "Пошук роботи", at))


def say(
    storage: LocalStorage, facil: Facil, ref: TopicRef, text: str, at: datetime, recognize: Rec | None = None
) -> list[ReplyEvent]:
    return list(reply(storage, facil, ALICE, ref, text, at, recognize=recognize, question=Q))


def again(
    storage: LocalStorage, facil: Facil, ref: TopicRef, at: datetime, recognize: Rec | None = None
) -> list[ReplyEvent]:
    return list(retry(storage, facil, ALICE, ref, at, recognize=recognize))


def upload(
    storage: LocalStorage,
    facil: Facil,
    ref: TopicRef,
    name: str,
    data: bytes,
    at: datetime,
    recognize: Rec | None = None,
    user: CurrentUser = ALICE,
) -> list[ReplyEvent]:
    from thinkhow.workspace import add_document

    return list(add_document(storage, facil, user, ref, name, data, at, recognize=recognize, question=Q))


def call_upload(
    storage: LocalStorage,
    facil: Facil,
    ref: TopicRef,
    name: str,
    data: bytes,
    at: datetime,
    user: CurrentUser = ALICE,
) -> Iterator[ReplyEvent]:
    """Only the call: the eager checks run here, nothing is iterated."""
    from thinkhow.workspace import add_document

    return add_document(storage, facil, user, ref, name, data, at, question=Q)


def drain_until_error(events: Iterator[ReplyEvent]) -> tuple[list[ReplyEvent], BaseException | None]:
    got: list[ReplyEvent] = []
    try:
        for event in events:
            got.append(event)
    except Exception as exc:  # noqa: BLE001 - the test inspects it
        return got, exc
    return got, None


def turns(storage: LocalStorage, ref: TopicRef, now: datetime) -> list[NumberedTurn]:
    view = open_topic(storage, ALICE, ref, now)
    return [t for s in view.sessions for t in s.turns]


def chosen(step_id: str, text: str, turn: int) -> MapUpdate:
    return MapUpdate(op="add", id=step_id, type="chosen_step", text=text, turn=f"t{turn}")


def with_chosen_step(storage: LocalStorage, at: datetime) -> TopicRef:
    """#1 the person's turn at `at`, #2 the facilitator's answer that writes the chosen step (turn t2)."""
    ref = new_topic(storage, at - M)
    say(storage, Facil(updates=[chosen("s1", STEP, 2)]), ref, "Хочу змінити роботу.", at)
    return ref


def txt(text: str) -> bytes:
    return text.encode("utf-8")


# --- the web -------------------------------------------------------------------------------------------


def make_client(tmp_path: Path, storage: LocalStorage, facil: Facil, now: datetime) -> TestClient:
    set_language(storage, ALICE, "uk-UA")
    set_language(storage, BOB, "uk-UA")
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
        now=lambda: now,
        speech=ScriptedSpeech(""),
    )
    return TestClient(create_app(deps), raise_server_exceptions=False, follow_redirects=False)


def page_url(ref: TopicRef) -> str:
    return f"/topics/{ref.uid}/{ref.topic_id}"


def document_url(ref: TopicRef) -> str:
    return f"/topics/{ref.uid}/{ref.topic_id}/document"


def catalog(name: str) -> dict[str, str]:
    data: dict[str, str] = json.loads((LOCALES / f"{name}.json").read_text(encoding="utf-8"))
    return data


def uk(key: str) -> str:
    words = catalog("uk")
    assert key in words, f"no key {key!r} in the uk catalog"
    return words[key]


def sse_events(body: str) -> list[tuple[str, Any]]:
    text = body.replace("\r\n", "\n")
    events: list[tuple[str, Any]] = []
    for block in text.strip("\n").split("\n\n"):
        name, data = "", None
        for line in block.split("\n"):
            if line.startswith("event:"):
                name = line[len("event:") :].strip()
            elif line.startswith("data:"):
                data = json.loads(line[len("data:") :].strip() or "null")
        if name:
            events.append((name, data))
    return events


class Tags(HTMLParser):
    """Every start tag in document order with its attributes, and the text inside each element by id."""

    def __init__(self, html: str) -> None:
        super().__init__(convert_charrefs=True)
        self.tags: list[tuple[str, dict[str, str | None]]] = []
        self._open: list[str | None] = []
        self.texts: dict[str, str] = {}
        self.feed(html)

    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "wbr"}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        self.tags.append((tag, a))
        if tag in self.VOID:
            return
        self._open.append(a.get("id"))
        if a.get("id"):
            self.texts.setdefault(str(a["id"]), "")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append((tag, dict(attrs)))

    def handle_endtag(self, tag: str) -> None:
        if tag in self.VOID:
            return
        if self._open:
            self._open.pop()

    def handle_data(self, data: str) -> None:
        for el in self._open:
            if el:
                self.texts[el] += data

    def index_of(self, element_id: str) -> int:
        for i, (_, a) in enumerate(self.tags):
            if a.get("id") == element_id:
                return i
        raise AssertionError(f"no element #{element_id} on the page")

    def by_id(self, element_id: str) -> tuple[str, dict[str, str | None]]:
        return self.tags[self.index_of(element_id)]
