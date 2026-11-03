"""Contract tests of document-upload: the invariants I1–I5, inputs chosen by hand from each «Domain».

Slice tester; from the contract `.engine/slices/document-upload.md`, not the code.
"""

from datetime import datetime
from pathlib import Path

import pytest
from du_fakes import (
    BOB,
    MAX,
    RESUME_DOCX_TEXT,
    RESUME_PDF_TEXT,
    S1,
    T0,
    Facil,
    M,
    PathFailStorage,
    again,
    call_upload,
    conversation_md,
    docx,
    drain_until_error,
    entries,
    file_bytes,
    new_topic,
    say,
    too_large,
    topic_files,
    turns,
    txt,
    upload,
)

from thinkhow.facilitation.types import Turn
from thinkhow.platform.storage import LocalStorage
from thinkhow.workspace import Answered, Failed, PendingAnswer, TopicNotFound, TopicRef


def frame(name: str, text: str) -> str:
    from thinkhow.facilitation.types import document_turn

    return document_turn(name, text)


def test_I1_every_reply_and_retry_gets_each_document_turn_as_its_frame_and_every_other_turn_as_stored(
    tmp_path: Path,
) -> None:
    # (a) zero documents: a plain reply, and a person who types «📎 x.txt» with no entry behind it
    storage = LocalStorage(tmp_path / "zero")
    ref = new_topic(storage)
    say(storage, Facil(["Так."]), ref, "📎 x.txt", T0)
    facil = Facil()
    say(storage, facil, ref, "Далі.", T0 + M)
    assert facil.contexts[0].history == [Turn("user", "📎 x.txt"), Turn("model", "Так.")]

    # (b) a document, an ordinary turn, a document whose answer failed and its retry, then a reply
    storage = LocalStorage(tmp_path / "mixed")
    ref = new_topic(storage)
    upload(storage, Facil(["Бачу резюме."]), ref, "resume.pdf", file_bytes("resume.pdf"), T0)
    say(storage, Facil(["Що саме?"]), ref, "Думка.", T0 + M)
    assert isinstance(
        upload(storage, Facil([None]), ref, "cv.docx", file_bytes("resume.docx"), T0 + 2 * M)[-1], Failed
    )
    retried = Facil(["Бачу докс."])
    again(storage, retried, ref, T0 + 3 * M)
    assert retried.contexts[0].text == frame("cv.docx", RESUME_DOCX_TEXT)
    first_four = [
        Turn("user", frame("resume.pdf", RESUME_PDF_TEXT)),
        Turn("model", "Бачу резюме."),
        Turn("user", "Думка."),
        Turn("model", "Що саме?"),
    ]
    assert retried.contexts[0].history == first_four
    later = Facil()
    say(storage, later, ref, "Підсумуй.", T0 + 4 * M)
    assert later.contexts[0].text == "Підсумуй."
    assert later.contexts[0].history == [
        *first_four,
        Turn("user", frame("cv.docx", RESUME_DOCX_TEXT)),
        Turn("model", "Бачу докс."),
    ]

    # (c) the same name twice: each turn its own text
    storage = LocalStorage(tmp_path / "twice")
    ref = new_topic(storage)
    upload(storage, Facil(["Раз."]), ref, "cv.txt", txt("Текст один"), T0)
    upload(storage, Facil(["Два."]), ref, "cv.txt", txt("Текст два"), T0 + M)
    later = Facil()
    say(storage, later, ref, "Порівняй.", T0 + 2 * M)
    assert later.contexts[0].history == [
        Turn("user", frame("cv.txt", "Текст один")),
        Turn("model", "Раз."),
        Turn("user", frame("cv.txt", "Текст два")),
        Turn("model", "Два."),
    ]

    # (d) a write failed during an upload: the orphan stays out of the ordinary turn at its number
    storage = PathFailStorage(tmp_path / "orphan")
    ref = new_topic(storage)
    storage.fail_suffix = "conversation.md"
    drain_until_error(call_upload(storage, Facil(), ref, "o.txt", txt("Сирота"), T0))
    storage.fail_suffix = None
    first = Facil(["Ок."])
    say(storage, first, ref, "Звичайне.", T0 + M)
    assert (first.contexts[0].turn_no, first.contexts[0].text) == (1, "Звичайне.")
    later = Facil()
    say(storage, later, ref, "Ще.", T0 + 2 * M)
    assert later.contexts[0].history == [Turn("user", "Звичайне."), Turn("model", "Ок.")]

    # (e) an orphan, then a re-upload of the same name at the same number: the last entry wins
    storage = PathFailStorage(tmp_path / "rewin")
    ref = new_topic(storage)
    storage.fail_suffix = "conversation.md"
    drain_until_error(call_upload(storage, Facil(), ref, "r.txt", txt("Стара"), T0))
    storage.fail_suffix = None
    own = Facil(["Нова."])
    upload(storage, own, ref, "r.txt", txt("Нова версія"), T0 + M)
    assert (own.contexts[0].turn_no, own.contexts[0].text) == (1, frame("r.txt", "Нова версія"))
    later = Facil()
    say(storage, later, ref, "Ще.", T0 + 2 * M)
    assert later.contexts[0].history == [Turn("user", frame("r.txt", "Нова версія")), Turn("model", "Нова.")]


def test_I2_a_refused_upload_leaves_every_stored_file_of_the_topic_byte_identical(tmp_path: Path) -> None:
    from thinkhow.platform.documents import Unreadable

    root = tmp_path / "data"
    storage = LocalStorage(root)
    ref = new_topic(storage)
    upload(storage, Facil(), ref, "base.txt", txt("ж" * (MAX - 10)), T0)  # an accepted one first
    refusals: list[tuple[str, bytes, type[BaseException] | None]] = [
        ("cv.doc", file_bytes("resume.docx"), Unreadable),  # format
        ("", txt("Текст"), Unreadable),  # an empty name: format
        ("scan.pdf", file_bytes("scan.pdf"), Unreadable),  # empty
        ("broken.pdf", b"%PDF-1.7 garbage", Unreadable),  # broken
        ("bad.txt", "café".encode("latin-1"), Unreadable),  # broken
        ("encrypted.pdf", file_bytes("encrypted.pdf"), Unreadable),  # encrypted
        ("eleven.txt", txt("з" * 11), None),  # DocumentTooLarge: MAX - 10 + 11
    ]
    for name, data, error in refusals:
        before = topic_files(root, ref)
        with pytest.raises(Exception) as caught:
            list(call_upload(storage, Facil(), ref, name, data, T0 + M))
        if error is None:
            assert too_large(caught.value), repr(caught.value)
        else:
            assert isinstance(caught.value, error), repr(caught.value)
        assert topic_files(root, ref) == before, name
    # a lawful upload after the refusals still fits exactly
    assert isinstance(upload(storage, Facil(), ref, "ten.txt", txt("и" * 10), T0 + 2 * M)[-1], Answered)
    # a zone-less now and a foreign topic
    before = topic_files(root, ref)
    with pytest.raises(ValueError):
        list(call_upload(storage, Facil(), ref, "cv.txt", txt("Резюме"), (T0 + 3 * M).replace(tzinfo=None)))
    with pytest.raises(TopicNotFound):
        list(call_upload(storage, Facil(), ref, "cv.txt", txt("Резюме"), T0 + 3 * M, user=BOB))
    assert topic_files(root, ref) == before
    # a missing topic: nothing appears
    missing = TopicRef(ref.uid, "t-000000000000")
    with pytest.raises(TopicNotFound):
        list(call_upload(storage, Facil(), missing, "cv.txt", txt("Резюме"), T0 + 3 * M))
    assert topic_files(root, missing) == {}
    # a pending answer
    pending_root = tmp_path / "pending"
    other = LocalStorage(pending_root)
    pref = new_topic(other)
    upload(other, Facil(), pref, "first.txt", txt("Перший"), T0)
    say(other, Facil([None]), pref, "Без відповіді.", T0 + M)
    before = topic_files(pending_root, pref)
    with pytest.raises(PendingAnswer):
        list(call_upload(other, Facil(), pref, "cv.txt", txt("Резюме"), T0 + 2 * M))
    assert topic_files(pending_root, pref) == before


def test_I3_conversation_md_holds_only_the_paperclip_and_the_cleaned_name(
    tmp_path: Path,
) -> None:
    storage = LocalStorage(tmp_path)
    ref = new_topic(storage)
    files = [
        ("resume.pdf", file_bytes("resume.pdf"), "resume.pdf", "Monobank"),
        ("/home/olena/Мої документи/cv.docx", docx([["Секретний абзац QWX"]]), "cv.docx", "QWX"),
        ("C:\\Docs\\план\n  на рік.md", txt("Рядок ZPL у плані"), "план на рік.md", "ZPL"),
        ("\tнотатки\r\nпро\tроботу.TXT", txt("Текст KJH"), "нотатки про роботу.TXT", "KJH"),
    ]
    at = T0
    for raw, data, _, _ in files:
        upload(storage, Facil([None]), ref, raw, data, at)  # failed answer, then a retry
        again(storage, Facil(), ref, at + M)
        at += 2 * M
    say(storage, Facil(), ref, "Підсумуй.", at)
    user_turns = [t.text for t in turns(storage, ref, at + M) if t.role == "user"]
    assert user_turns == ["📎 " + clean for _, _, clean, _ in files] + ["Підсумуй."]
    stored = conversation_md(storage, ref)
    for _, _, clean, secret in files:
        assert secret not in stored, secret
        assert "📎 " + clean in stored, clean


def test_I4_after_any_accepted_upload_the_topics_documents_hold_at_most_max_document_chars(
    tmp_path: Path,
) -> None:
    def total(storage: LocalStorage, ref: TopicRef) -> int:
        return sum(len(str(e["text"])) for e in entries(storage, ref))

    def refused(storage: LocalStorage, ref: TopicRef, name: str, data: bytes, at: datetime) -> None:
        with pytest.raises(Exception) as caught:
            list(call_upload(storage, Facil(), ref, name, data, at))
        assert too_large(caught.value), repr(caught.value)

    # uploads one after another, each under the limit alone, together at the edge
    storage = LocalStorage(tmp_path / "seq")
    ref = new_topic(storage)
    at = T0
    for size in (100_000, 60_000, 39_999):
        upload(storage, Facil(), ref, f"f{size}.txt", txt("а" * size), at)
        at += M
        assert total(storage, ref) <= MAX
    refused(storage, ref, "two.txt", txt("бб"), at)
    upload(storage, Facil(), ref, "one.txt", txt("б"), at)
    assert total(storage, ref) == MAX
    refused(storage, ref, "more.txt", txt("в"), at + M)
    assert total(storage, ref) == MAX

    # an orphan entry counts too
    failing = PathFailStorage(tmp_path / "orphan")
    oref = new_topic(failing)
    failing.fail_suffix = "conversation.md"
    drain_until_error(call_upload(failing, Facil(), oref, "o.txt", txt("о" * 150_000), T0))
    failing.fail_suffix = None
    refused(failing, oref, "x.txt", txt("х" * 50_001), T0 + M)
    upload(failing, Facil(), oref, "y.txt", txt("у" * 50_000), T0 + M + S1)
    assert total(failing, oref) == MAX
    refused(failing, oref, "z.txt", txt("з"), T0 + 2 * M)


def test_I5_a_txt_or_md_file_in_utf8_or_utf16_with_a_bom_comes_back_as_its_own_text() -> None:
    from thinkhow.platform.documents import extract

    texts = [
        ("x", "x"),
        ("Один рядок", "Один рядок"),
        ("  Відступ  всередині\tі таб  ", "Відступ  всередині\tі таб"),
        ("\r\n\r\nРядок 1\r\n\r\n\r\nРядок 3\rРядок 4\n\n", "Рядок 1\n\n\nРядок 3\nРядок 4"),
        ("emoji 🙂 і 𝄞 нота\n  * пункт", "emoji 🙂 і 𝄞 нота\n  * пункт"),
        ("Latin-1 що не є: é ü ß — «лапки»", "Latin-1 що не є: é ü ß — «лапки»"),
    ]
    encodings = [
        ("utf-8", b""),
        ("utf-8", b"\xef\xbb\xbf"),
        ("utf-16-le", b"\xff\xfe"),
        ("utf-16-be", b"\xfe\xff"),
    ]
    names = ["a.txt", "a.md", "a.markdown", "A.TXT", "a.Md", "a.MarkDown"]
    for raw, expected in texts:
        for codec, bom in encodings:
            for name in names:
                got = extract(name, bom + raw.encode(codec))
                assert got == expected, (raw, codec, bom, name, got)
