"""Contract tests of document-upload: `workspace.add_document` and what `_answer` gives the model.

Slice tester; from the contract `.engine/slices/document-upload.md`, not the code.
"""

from pathlib import Path

import pytest
from du_fakes import (
    ALICE,
    BOB,
    DAY,
    MAX,
    RESUME_PDF_TEXT,
    T0,
    Facil,
    M,
    PathFailStorage,
    Q,
    Rec,
    StorageBroke,
    again,
    call_upload,
    conversation_md,
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
    with_chosen_step,
    worked,
)

from thinkhow.facilitation.types import Turn
from thinkhow.platform.storage import LocalStorage
from thinkhow.workspace import (
    Answered,
    Delta,
    Failed,
    PendingAnswer,
    Saved,
    TopicNotFound,
    TopicRef,
    open_topic,
    step_results_for_learning,
)


def frame(name: str, text: str) -> str:
    from thinkhow.facilitation.types import document_turn

    return document_turn(name, text)


def three(entry: dict[str, object]) -> tuple[object, object, object]:
    return (entry["turn"], entry["name"], entry["text"])


# --- the accepted upload ---------------------------------------------------------------------------


def test_an_upload_streams_saved_then_the_answer_and_stores_the_paperclip_turn(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    ref = new_topic(storage)
    got = upload(
        storage, Facil(["Бачу досвід у fintech. Що далі?"]), ref, "resume.pdf", file_bytes("resume.pdf"), T0
    )
    assert got[0] == Saved(1)
    assert Delta("Бачу досвід у fintech. Що далі?") in got
    assert got[-1] == Answered(2)
    assert [(t.no, t.role, t.text) for t in turns(storage, ref, T0 + M)] == [
        (1, "user", "📎 resume.pdf"),
        (2, "model", "Бачу досвід у fintech. Що далі?"),
    ]


def test_the_uploads_own_answer_reads_the_frame_of_the_document_as_the_current_turn(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    ref = new_topic(storage)
    say(storage, Facil(), ref, "Шукаю роботу.", T0)
    facil = Facil()
    upload(storage, facil, ref, "resume.pdf", file_bytes("resume.pdf"), T0 + M)
    (ctx,) = facil.contexts
    assert ctx.turn_no == 3
    assert ctx.text == frame("resume.pdf", RESUME_PDF_TEXT)
    assert ctx.history == [Turn("user", "Шукаю роботу."), Turn("model", "Добре. Що далі?")]


def test_the_entry_turn_name_text_is_appended_to_documents_json(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    ref = new_topic(storage)
    upload(storage, Facil(), ref, "resume.pdf", file_bytes("resume.pdf"), T0)
    upload(storage, Facil(), ref, "notes.txt", txt("Мої нотатки"), T0 + M)
    assert [three(e) for e in entries(storage, ref)] == [
        (1, "resume.pdf", RESUME_PDF_TEXT),
        (3, "notes.txt", "Мої нотатки"),
    ]


def test_the_name_is_cleaned_in_the_turn_and_in_the_entry(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    ref = new_topic(storage)
    names = [
        ("C:\\Users\\Олена\\CV  final\n v2.txt", "CV final v2.txt"),
        ("docs/2024/notes.md", "notes.md"),
        ("\t my\r\n\tnotes.markdown", "my notes.markdown"),
        ("a/b\\c/d e.txt", "d e.txt"),
    ]
    at = T0
    for raw, _ in names:
        upload(storage, Facil(), ref, raw, txt("Текст"), at)
        at += M
    user_turns = [t.text for t in turns(storage, ref, at) if t.role == "user"]
    assert user_turns == ["📎 " + clean for _, clean in names]
    assert [e["name"] for e in entries(storage, ref)] == [clean for _, clean in names]


def test_an_upload_after_the_break_opens_a_new_session(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    ref = new_topic(storage)
    say(storage, Facil(), ref, "Шукаю роботу.", T0)
    got = upload(storage, Facil(), ref, "cv.txt", txt("Резюме"), T0 + DAY)
    assert got[0] == Saved(3)
    view = open_topic(storage, ALICE, ref, T0 + DAY + M)
    assert len(view.sessions) == 2
    assert [t.text for t in view.sessions[-1].turns][0] == "📎 cv.txt"


def test_on_a_return_the_step_question_comes_before_the_document_turn(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    ref = with_chosen_step(storage, T0)  # #1 the person, #2 the facilitator writes the step
    back = T0 + DAY
    shown = open_topic(storage, ALICE, ref, back, question=Q).step_question
    assert shown is not None
    got = upload(storage, Facil(), ref, "cv.txt", txt("Резюме"), back)
    assert got[0] == Saved(4)
    assert [(t.no, t.role, t.text) for t in turns(storage, ref, back + M)][2:4] == [
        (3, "model", shown),
        (4, "user", "📎 cv.txt"),
    ]
    assert [three(e) for e in entries(storage, ref)] == [(4, "cv.txt", "Резюме")]


# --- Seam 2: what the model sees later ------------------------------------------------------------------


def test_a_later_reply_gets_the_frame_at_the_document_turn_and_the_file_keeps_the_paperclip(
    tmp_path: Path,
) -> None:
    storage = LocalStorage(tmp_path)
    ref = new_topic(storage)
    upload(storage, Facil(["Бачу fintech."]), ref, "resume.pdf", file_bytes("resume.pdf"), T0)
    facil = Facil()
    say(storage, facil, ref, "Що мені з цим робити?", T0 + DAY)  # a new session, «after reload»
    (ctx,) = facil.contexts
    assert ctx.text == "Що мені з цим робити?"
    assert ctx.history == [Turn("user", frame("resume.pdf", RESUME_PDF_TEXT)), Turn("model", "Бачу fintech.")]
    stored = conversation_md(storage, ref)
    assert "📎 resume.pdf" in stored
    assert "Monobank" not in stored


def test_a_retry_of_a_failed_upload_answers_from_the_frame(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    ref = new_topic(storage)
    got = upload(storage, Facil([None]), ref, "resume.pdf", file_bytes("resume.pdf"), T0)
    assert got[0] == Saved(1) and isinstance(got[-1], Failed)
    facil = Facil(["Тепер бачу."])
    assert again(storage, facil, ref, T0 + M)[-1] == Answered(2)
    (ctx,) = facil.contexts
    assert ctx.turn_no == 1
    assert ctx.text == frame("resume.pdf", RESUME_PDF_TEXT)
    assert ctx.history == []
    assert turns(storage, ref, T0 + 2 * M)[0].text == "📎 resume.pdf"


def test_two_uploads_of_the_same_name_each_keep_their_own_text(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    ref = new_topic(storage)
    upload(storage, Facil(["Перша."]), ref, "resume.txt", txt("Версія перша"), T0)
    upload(storage, Facil(["Друга."]), ref, "resume.txt", txt("Версія друга"), T0 + M)
    facil = Facil()
    say(storage, facil, ref, "Яка краща?", T0 + 2 * M)
    assert facil.contexts[0].history == [
        Turn("user", frame("resume.txt", "Версія перша")),
        Turn("model", "Перша."),
        Turn("user", frame("resume.txt", "Версія друга")),
        Turn("model", "Друга."),
    ]


def test_recognize_is_not_run_for_a_document_turn_from_the_upload_or_its_retry(tmp_path: Path) -> None:
    # the upload's own answer
    storage = LocalStorage(tmp_path / "a")
    ref = with_chosen_step(storage, T0)
    rec = Rec(worked())
    upload(storage, Facil(), ref, "cv.txt", txt("Резюме"), T0 + DAY, recognize=rec)
    assert rec.calls == []
    assert [r.outcome for r in step_results_for_learning(storage, ref)] == [None]
    # the answer failed, then a retry of the document turn
    storage = LocalStorage(tmp_path / "b")
    ref = with_chosen_step(storage, T0)
    rec = Rec(worked())
    got = upload(storage, Facil([None]), ref, "cv.txt", txt("Резюме"), T0 + DAY, recognize=rec)
    assert isinstance(got[-1], Failed)
    assert again(storage, Facil(), ref, T0 + DAY + M, recognize=rec)[-1] == Answered(5)
    assert rec.calls == []
    assert [r.outcome for r in step_results_for_learning(storage, ref)] == [None]


# --- Seam 2b: a write that fails mid-upload ---------------------------------------------------------------


def test_a_failed_conversation_write_raises_before_saved_and_leaves_the_entry(tmp_path: Path) -> None:
    storage = PathFailStorage(tmp_path)
    ref = new_topic(storage)
    say(storage, Facil(), ref, "Шукаю роботу.", T0)
    storage.fail_suffix = "conversation.md"
    got, exc = drain_until_error(call_upload(storage, Facil(), ref, "c.txt", txt("Текст C"), T0 + M))
    assert isinstance(exc, StorageBroke), exc
    assert not any(isinstance(e, Saved) for e in got), got
    assert [three(e) for e in entries(storage, ref)] == [(3, "c.txt", "Текст C")]


def test_a_failed_documents_write_raises_before_saved_and_leaves_the_conversation_untouched(
    tmp_path: Path,
) -> None:
    storage = PathFailStorage(tmp_path)
    ref = new_topic(storage)
    say(storage, Facil(), ref, "Шукаю роботу.", T0)
    before = conversation_md(storage, ref)
    storage.fail_suffix = "documents.json"
    got, exc = drain_until_error(call_upload(storage, Facil(), ref, "c.txt", txt("Текст C"), T0 + M))
    assert isinstance(exc, StorageBroke), exc
    assert not any(isinstance(e, Saved) for e in got), got
    assert conversation_md(storage, ref) == before


def test_an_orphan_entry_does_not_replace_the_ordinary_turn_at_its_number(tmp_path: Path) -> None:
    storage = PathFailStorage(tmp_path)
    ref = new_topic(storage)
    say(storage, Facil(), ref, "Шукаю роботу.", T0)
    storage.fail_suffix = "conversation.md"
    drain_until_error(call_upload(storage, Facil(), ref, "c.txt", txt("Текст C"), T0 + M))
    storage.fail_suffix = None
    facil = Facil(["Зрозуміло."])
    say(storage, facil, ref, "Звичайна думка.", T0 + 2 * M)
    assert (facil.contexts[0].turn_no, facil.contexts[0].text) == (3, "Звичайна думка.")
    say(storage, facil, ref, "Ще одна.", T0 + 3 * M)
    assert facil.contexts[1].history[2] == Turn("user", "Звичайна думка.")


def test_after_an_orphan_the_upload_at_the_same_number_answers_from_its_own_text(tmp_path: Path) -> None:
    # the same name, a different text
    storage = PathFailStorage(tmp_path / "same")
    ref = new_topic(storage)
    say(storage, Facil(), ref, "Шукаю роботу.", T0)
    storage.fail_suffix = "conversation.md"
    drain_until_error(call_upload(storage, Facil(), ref, "resume.txt", txt("Текст T1"), T0 + M))
    storage.fail_suffix = None
    facil = Facil(["Бачу T2."])
    assert upload(storage, facil, ref, "resume.txt", txt("Текст T2"), T0 + 2 * M)[0] == Saved(3)
    assert facil.contexts[0].text == frame("resume.txt", "Текст T2")
    later = Facil()
    say(storage, later, ref, "Далі.", T0 + 3 * M)
    assert later.contexts[0].history[2] == Turn("user", frame("resume.txt", "Текст T2"))
    # another name at the same number
    storage = PathFailStorage(tmp_path / "other")
    ref = new_topic(storage)
    say(storage, Facil(), ref, "Шукаю роботу.", T0)
    storage.fail_suffix = "conversation.md"
    drain_until_error(call_upload(storage, Facil(), ref, "a.txt", txt("Текст A"), T0 + M))
    storage.fail_suffix = None
    facil = Facil()
    assert upload(storage, facil, ref, "b.txt", txt("Текст B"), T0 + 2 * M)[0] == Saved(3)
    assert facil.contexts[0].text == frame("b.txt", "Текст B")
    later = Facil()
    say(storage, later, ref, "Далі.", T0 + 3 * M)
    assert later.contexts[0].history[2] == Turn("user", frame("b.txt", "Текст B"))


# --- the eager checks and Seam 3 --------------------------------------------------------------------------


def _pending(storage: LocalStorage) -> TopicRef:
    ref = new_topic(storage)
    assert isinstance(say(storage, Facil([None]), ref, "Без відповіді.", T0)[-1], Failed)
    return ref


def test_the_eager_checks_run_at_the_call_in_the_contracts_order(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    ref = new_topic(storage)
    broken = b"\xff\xfe\x00\xd8"
    naive = T0.replace(tzinfo=None)
    with pytest.raises(ValueError):
        call_upload(storage, Facil(), ref, "x.txt", broken, naive, user=BOB)  # the zone before anything
    with pytest.raises(TopicNotFound):
        call_upload(storage, Facil(), ref, "x.txt", broken, T0, user=BOB)  # _can_write before extract
    pending = _pending(LocalStorage(tmp_path / "p"))
    with pytest.raises(PendingAnswer):
        call_upload(LocalStorage(tmp_path / "p"), Facil(), pending, "x.txt", broken, T0 + M)
    with pytest.raises(PendingAnswer):
        call_upload(LocalStorage(tmp_path / "p"), Facil(), pending, "x.txt", txt("а" * (MAX + 1)), T0 + M)
    from thinkhow.platform.documents import Unreadable

    with pytest.raises(Unreadable):  # extract before the size
        call_upload(storage, Facil(), ref, "big.txt", txt("а" * (MAX + 1)) + b"\xff", T0)


def test_a_foreign_or_missing_topic_is_topic_not_found(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    ref = new_topic(storage)
    with pytest.raises(TopicNotFound):
        call_upload(storage, Facil(), ref, "cv.txt", txt("Резюме"), T0, user=BOB)
    with pytest.raises(TopicNotFound):
        call_upload(storage, Facil(), TopicRef(ALICE.id, "t-000000000000"), "cv.txt", txt("Резюме"), T0)


def test_a_pending_answer_refuses_the_upload(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    ref = _pending(storage)
    with pytest.raises(PendingAnswer):
        call_upload(storage, Facil(), ref, "cv.txt", txt("Резюме"), T0 + M)


def test_unreadable_passes_up_from_add_document(tmp_path: Path) -> None:
    from thinkhow.platform.documents import Unreadable

    storage = LocalStorage(tmp_path)
    ref = new_topic(storage)
    with pytest.raises(Unreadable):
        call_upload(storage, Facil(), ref, "scan.pdf", file_bytes("scan.pdf"), T0)
    with pytest.raises(Unreadable):
        call_upload(storage, Facil(), ref, "cv.doc", file_bytes("resume.docx"), T0)


def test_the_limit_accepts_exactly_max_document_chars_together_and_refuses_one_more(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    ref = new_topic(storage)
    assert upload(storage, Facil(), ref, "a.txt", txt("а" * 150_000), T0)[0] == Saved(1)
    assert upload(storage, Facil(), ref, "b.txt", txt("б" * 50_000), T0 + M)[0] == Saved(3)
    with pytest.raises(Exception) as caught:
        call_upload(storage, Facil(), ref, "c.txt", txt("в"), T0 + 2 * M)
    assert too_large(caught.value), repr(caught.value)
    alone = LocalStorage(tmp_path / "alone")
    one = new_topic(alone)
    with pytest.raises(Exception) as caught:
        call_upload(alone, Facil(), one, "big.txt", txt("г" * (MAX + 1)), T0)
    assert too_large(caught.value), repr(caught.value)
    assert upload(alone, Facil(), one, "max.txt", txt("г" * MAX), T0 + M)[0] == Saved(1)
    assert topic_files(tmp_path / "alone", one)  # the accepted one is stored
