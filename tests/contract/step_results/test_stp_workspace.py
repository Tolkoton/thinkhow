"""Contract tests of step-results (learning-loop S6): when the question shows, when it becomes a turn,
the record in steps.json and the recognition in the reply flow (Seams 1–3).

Slice tester; from the contract `.engine/slices/step-results.md`, not the code.
"""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from stp_fakes import (
    ALICE,
    DAY,
    OWNER,
    S1,
    SILENCE,
    SKIPPED,
    STEP,
    STEP_ID,
    T0,
    Facil,
    H,
    M,
    Q,
    Rec,
    again,
    chosen,
    new_topic,
    outcome,
    question_now,
    say,
    turn_no,
    turns,
    with_chosen_step,
)

from thinkhow.facilitation.types import Decision, FacilitationContext, Rev, Turn
from thinkhow.platform.storage import LocalStorage
from thinkhow.workspace import (
    Answered,
    Delta,
    Failed,
    Saved,
    StepResult,
    open_topic,
    reply,
    step_results_for_learning,
    topic_routing,
)

ANSWER_TEXT = "Вийшло: поговорив з трьома, двоє готові платити, стало ясніше"


def _stdout_events(out: str, name: str) -> list[dict[str, Any]]:
    found = []
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("{"):
            obj = json.loads(line)
            if isinstance(obj, dict) and obj.get("event") == name:
                found.append(obj)
    return found


def _stamp(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# --- Seam 1: when the question shows --------------------------------------------------------------


def test_seam1_question_shows_one_second_past_silence_and_not_one_second_before(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    ref = with_chosen_step(storage, T0)  # the last turn (#2) at T0
    before = question_now(storage, ref, T0 + SILENCE - S1)
    after = question_now(storage, ref, T0 + SILENCE + S1)
    assert before is None
    assert after is not None and STEP in after


def test_seam1_no_question_without_a_chosen_step_or_once_its_record_exists(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    bare = new_topic(storage, ALICE, T0 - M)
    say(storage, bare, "Хочу відкрити кав'ярню.", T0, Facil(updates=[]))
    asked = with_chosen_step(storage, T0)
    say(storage, asked, ANSWER_TEXT, T0 + DAY)  # the question is asked: steps.json has its record
    control = with_chosen_step(storage, T0)
    assert question_now(storage, control, T0 + 3 * DAY) is not None
    assert question_now(storage, bare, T0 + 3 * DAY) is None
    assert question_now(storage, asked, T0 + 3 * DAY) is None


def test_seam1_of_several_chosen_steps_the_question_is_about_the_latest_without_a_record(
    tmp_path: Path,
) -> None:
    storage = LocalStorage(tmp_path)
    ref = with_chosen_step(storage, T0, step_id="old", step="Порахувати витрати")
    say(
        storage,
        ref,
        "А ще думаю про оренду.",
        T0 + M,
        Facil(updates=[chosen("new", "Подзвонити орендодавцю", 4)]),
    )
    shown = question_now(storage, ref, T0 + M + DAY)
    assert shown is not None
    assert "Подзвонити орендодавцю" in shown
    assert "Порахувати витрати" not in shown


def test_seam1_a_session_closed_by_the_legacy_marker_shows_the_question(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    ref = with_chosen_step(storage, T0)
    legacy = "\n".join(
        [
            "<!-- thinkhow:format 1 -->",
            "# Кав'ярня",
            "<!-- thinkhow:session 1 -->",
            f"<!-- thinkhow:turn 1 user {_stamp(T0)} -->",
            "Хочу відкрити кав'ярню.",
            f"<!-- thinkhow:turn 2 model {_stamp(T0 + S1)} -->",
            "Добре. Що далі?",
            f"<!-- thinkhow:closed 1 {_stamp(T0 + M)} -->",
        ]
    )
    storage.write(
        "users", f"{ref.uid}/{ref.topic_id}/conversation.md", (legacy + "\n").encode("utf-8"), "text/markdown"
    )
    shown = question_now(storage, ref, T0 + H)  # one hour: no silence, but the marker closed the session
    assert shown is not None and STEP in shown


def test_seam1_the_question_shows_to_the_topics_owner_only(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    ref = with_chosen_step(storage, T0)
    assert open_topic(storage, ALICE, ref, T0 + DAY, question=Q).step_question is not None
    assert open_topic(storage, OWNER, ref, T0 + DAY, question=Q).step_question is None


# --- Seam 2: the question becomes a turn -----------------------------------------------------------


def _ask(context: FacilitationContext) -> Decision:
    return Decision(
        turn=context.turn_no,
        rev=Rev(rev=1, n=3),
        kind="ask",
        profile=None,
        candidates=[],
        card_id=None,
        end=None,
        why="питаю",
    )


def test_seam2_order_and_numbers_of_the_question_turn_the_persons_turn_and_the_answer(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    ref = with_chosen_step(storage, T0)  # N = 2
    back = T0 + DAY
    shown = question_now(storage, ref, back)
    assert shown is not None
    facil = Facil(answer="Чудово. Хто третій?", decision=_ask)
    events = say(storage, ref, ANSWER_TEXT, back, facil, Rec(outcome()))
    assert events[0] == Saved(4)
    assert events[-1] == Answered(5)
    assert all(isinstance(e, Delta) for e in events[1:-1]) and events[1:-1]
    view = open_topic(storage, ALICE, ref, back + M, question=Q)
    session_of = {t.no: s.no for s in view.sessions for t in s.turns}
    assert session_of[3] != session_of[2]  # a new session
    assert session_of[3] == session_of[4] == session_of[5]
    q, person, answer = (turn_no(storage, ref, back + M, n) for n in (3, 4, 5))
    assert (q.role, q.text) == ("model", shown)
    assert (person.role, person.text) == ("user", ANSWER_TEXT)
    assert (answer.role, answer.text) == ("model", "Чудово. Хто третій?")
    assert [d.turn for d in topic_routing(storage, ref)] == [4]
    assert [c.turn_no for c in facil.contexts] == [4]
    assert Turn("model", shown) in facil.contexts[0].history


def test_without_recognize_the_record_stays_with_outcome_none(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    ref = with_chosen_step(storage, T0)
    back = T0 + DAY
    say(storage, ref, ANSWER_TEXT, back)
    view = open_topic(storage, ALICE, ref, back + M, question=Q)
    assert view.steps == (
        StepResult(step_id=STEP_ID, step=STEP, asked_turn=3, outcome=None, clearer=None, said="", at=back),
    )


def test_recognize_gets_the_step_the_question_and_the_persons_text_and_updates_the_record(
    tmp_path: Path,
) -> None:
    storage = LocalStorage(tmp_path)
    ref = with_chosen_step(storage, T0)
    back = T0 + DAY
    shown = question_now(storage, ref, back)
    rec = Rec(outcome("unexpected", "partly", "клієнти хочуть доставку"))
    say(storage, ref, ANSWER_TEXT, back, recognize=rec)
    assert rec.calls == [(STEP, shown, ANSWER_TEXT)]
    (got,) = open_topic(storage, ALICE, ref, back + M, question=Q).steps
    assert (got.step_id, got.step, got.asked_turn) == (STEP_ID, STEP, 3)
    assert (got.outcome, got.clearer, got.said) == ("unexpected", "partly", "клієнти хочуть доставку")


def test_step_results_for_learning_are_the_records_of_steps_json_without_an_access_rule(
    tmp_path: Path,
) -> None:
    storage = LocalStorage(tmp_path)
    ref = with_chosen_step(storage, T0)
    say(storage, ref, ANSWER_TEXT, T0 + DAY, recognize=Rec(outcome("not_worked", "no", "ніхто не прийшов")))
    got = step_results_for_learning(storage, ref)
    assert [(r.step_id, r.step, r.asked_turn, r.outcome, r.clearer, r.said) for r in got] == [
        (STEP_ID, STEP, 3, "not_worked", "no", "ніхто не прийшов")
    ]
    assert list(open_topic(storage, ALICE, ref, T0 + DAY + M, question=Q).steps) == got


# --- Seam 3: recognition does not break the answer ------------------------------------------------


def test_seam3_recognize_runs_after_the_answer_is_written_and_steps_json_before_answered(
    tmp_path: Path,
) -> None:
    storage = LocalStorage(tmp_path)
    ref = with_chosen_step(storage, T0)
    back = T0 + DAY
    seen: list[list[int]] = []
    rec = Rec(outcome("worked", "yes", "двоє готові платити"))
    rec.on_call = lambda: seen.append([t.no for t in turns(storage, ref, back)])
    flow = reply(storage, Facil(answer="Чудово."), ALICE, ref, ANSWER_TEXT, back, recognize=rec, question=Q)
    at_answered = None
    for event in flow:
        if isinstance(event, Answered):
            at_answered = open_topic(storage, ALICE, ref, back, question=Q).steps
        else:
            assert not rec.calls or isinstance(event, Answered), f"recognize ran before {event}"
    assert seen and 5 in seen[0]
    assert at_answered is not None
    assert [(r.outcome, r.clearer, r.said) for r in at_answered] == [("worked", "yes", "двоє готові платити")]


def test_seam3_recognize_raising_keeps_the_answer_and_the_record_and_logs_the_type(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    storage = LocalStorage(tmp_path)
    ref = with_chosen_step(storage, T0)
    back = T0 + DAY
    capsys.readouterr()
    events = say(
        storage, ref, ANSWER_TEXT, back, Facil(answer="Чудово."), Rec(fail=RuntimeError("зламалось"))
    )
    out = capsys.readouterr().out
    assert events[0] == Saved(4) and events[-1] == Answered(5)
    assert not any(isinstance(e, Failed) for e in events)
    assert turn_no(storage, ref, back, 5).text == "Чудово."
    (got,) = open_topic(storage, ALICE, ref, back, question=Q).steps
    assert (got.asked_turn, got.outcome, got.clearer, got.said) == (3, None, None, "")
    logged = _stdout_events(out, "step_recognize_failed")
    assert len(logged) == 1
    assert "RuntimeError" in json.dumps(logged[0], ensure_ascii=False)
    assert ANSWER_TEXT not in out


def test_seam3_answered_false_leaves_the_record_unchanged(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    ref = with_chosen_step(storage, T0)
    back = T0 + DAY
    rec = Rec(SKIPPED)
    say(storage, ref, "Сьогодні хочу про інше: про меню.", back, recognize=rec)
    assert len(rec.calls) == 1
    assert open_topic(storage, ALICE, ref, back, question=Q).steps == (
        StepResult(step_id=STEP_ID, step=STEP, asked_turn=3, outcome=None, clearer=None, said="", at=back),
    )


def test_seam3_a_failed_answer_does_not_call_recognize_and_the_record_stays(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    ref = with_chosen_step(storage, T0)
    back = T0 + DAY
    rec = Rec(outcome())
    events = say(storage, ref, ANSWER_TEXT, back, Facil(answer=None), rec)
    assert events[0] == Saved(4)
    assert isinstance(events[-1], Failed)
    assert rec.calls == []
    assert [(r.step_id, r.asked_turn, r.outcome) for r in open_topic(storage, ALICE, ref, back).steps] == [
        (STEP_ID, 3, None)
    ]
    assert question_now(storage, ref, back + DAY) is None


def test_seam3_retry_of_the_turn_right_after_the_question_calls_recognize_before_answered(
    tmp_path: Path,
) -> None:
    storage = LocalStorage(tmp_path)
    ref = with_chosen_step(storage, T0)
    back = T0 + DAY
    shown = question_now(storage, ref, back)
    say(storage, ref, ANSWER_TEXT, back, Facil(answer=None), Rec(outcome()))
    rec = Rec(outcome("worked", "partly", "двоє з трьох"))
    flow = again(storage, ref, back + M, Facil(answer="Тепер відповідаю."), rec)
    assert flow[-1] == Answered(5)
    assert rec.calls == [(STEP, shown, ANSWER_TEXT)]
    (got,) = open_topic(storage, ALICE, ref, back + M, question=Q).steps
    assert (got.asked_turn, got.outcome, got.clearer, got.said) == (3, "worked", "partly", "двоє з трьох")


def test_recognize_is_called_only_for_the_answer_to_the_turn_right_after_the_question(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    ref = with_chosen_step(storage, T0)
    back = T0 + DAY
    say(storage, ref, ANSWER_TEXT, back)  # #3 question, #4, #5 — no recognize: outcome None
    rec = Rec(outcome())
    say(storage, ref, "А що з меню?", back + M, recognize=rec)  # #6, #7
    say(storage, ref, "І з цінами?", back + 2 * M, Facil(answer=None), rec)  # #8 unanswered
    again(storage, ref, back + 3 * M, recognize=rec)  # #9
    assert rec.calls == []
    assert [t.no for t in turns(storage, ref, back + 3 * M)] == list(range(1, 10))
