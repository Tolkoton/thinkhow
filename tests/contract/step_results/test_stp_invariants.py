"""Invariant tests of step-results (learning-loop S6): I1–I3, inputs chosen by hand from each «Domain».

Slice tester; from the contract `.engine/slices/step-results.md`, not the code.
"""

import re
from datetime import datetime
from pathlib import Path

from stp_fakes import (
    ALICE,
    DAY,
    S1,
    SILENCE,
    SKIPPED,
    STEP_ID,
    T0,
    Facil,
    H,
    M,
    Rec,
    ScenarioLlm,
    again,
    chosen,
    one_observation,
    outcome,
    question_now,
    say,
    turn_no,
    turns,
    uk,
    with_chosen_step,
)

from thinkhow.learning.analyze import analyze
from thinkhow.platform.storage import LocalStorage
from thinkhow.workspace import TopicRef, open_topic


def _records(storage: LocalStorage, ref: TopicRef, now: datetime, step_id: str) -> int:
    return sum(1 for r in open_topic(storage, ALICE, ref, now).steps if r.step_id == step_id)


def _question_turns(storage: LocalStorage, ref: TopicRef, now: datetime, question: str) -> int:
    return sum(1 for t in turns(storage, ref, now) if t.role == "model" and t.text == question)


def test_I1_the_question_about_a_step_is_asked_at_most_once(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)

    # A: skipped, then pauses below and above SILENCE, a raising recognize, no recognize; then a new step
    a = with_chosen_step(storage, T0)
    t = T0 + DAY
    q_a = question_now(storage, a, t)
    assert q_a is not None
    say(storage, a, "Сьогодні про інше.", t, recognize=Rec(SKIPPED))
    t += M
    say(storage, a, "Ще одне.", t, recognize=Rec(SKIPPED))
    t += SILENCE - S1
    say(storage, a, "Майже через добу.", t, recognize=Rec(SKIPPED))
    for recognize in (Rec(fail=RuntimeError("x")), None, Rec(SKIPPED)):
        t += DAY
        assert question_now(storage, a, t) is None
        say(storage, a, "Знову повернулась.", t, recognize=recognize)
    say(storage, a, "А тепер оберу інше.", t + M, Facil(updates=[chosen("s2", "Подзвонити орендодавцю", 16)]))
    t += M + DAY
    q_a2 = question_now(storage, a, t)
    assert q_a2 is not None and "Подзвонити орендодавцю" in q_a2
    say(storage, a, "Подзвонив.", t, recognize=Rec(outcome()))
    t += DAY
    assert question_now(storage, a, t) is None
    say(storage, a, "І ще раз.", t, recognize=Rec(outcome()))
    assert _records(storage, a, t, STEP_ID) == 1
    assert _records(storage, a, t, "s2") == 1
    assert _question_turns(storage, a, t, q_a) == 1
    assert _question_turns(storage, a, t, q_a2) == 1

    # B: the answer to the question fails, retry; then two returns
    b = with_chosen_step(storage, T0)
    t = T0 + DAY
    q_b = question_now(storage, b, t)
    assert q_b is not None
    say(storage, b, "Вийшло.", t, Facil(answer=None), Rec(outcome()))
    again(storage, b, t + M, recognize=Rec(outcome()))
    for _ in range(2):
        t += DAY
        assert question_now(storage, b, t) is None
        say(storage, b, "Повернувся.", t, recognize=Rec(outcome()))
    assert _records(storage, b, t, STEP_ID) == 1
    assert _question_turns(storage, b, t, q_b) == 1

    # C: answered and recognized, then returns with every kind of recognize
    c = with_chosen_step(storage, T0)
    t = T0 + DAY
    q_c = question_now(storage, c, t)
    assert q_c is not None
    say(storage, c, "Вийшло.", t, recognize=Rec(outcome("worked", "yes", "вийшло")))
    for recognize in (Rec(outcome("not_worked", "no", "ні")), Rec(SKIPPED), Rec(fail=ValueError("y"))):
        t += DAY
        say(storage, c, "Повернулась.", t, recognize=recognize)
    assert _records(storage, c, t, STEP_ID) == 1
    assert _question_turns(storage, c, t, q_c) == 1


def test_I2_the_persons_turn_is_never_lost_with_or_without_the_question(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    texts = {
        "raises": "Вийшло «так собі».\nДругий рядок: 50% — ок",
        "fails": "Не вийшло: ніхто не прийшов",
        "skipped": "Сьогодні хочу про меню, а не про крок",
        "none": "Несподівано — всі хочуть доставку!",
    }
    cases = {
        "raises": (Facil(), Rec(fail=RuntimeError("boom"))),
        "fails": (Facil(answer=None), Rec(outcome())),
        "skipped": (Facil(), Rec(SKIPPED)),
        "none": (Facil(answer=None), Rec(fail=KeyError("k"))),
    }
    back = T0 + DAY
    for name, (facil, rec) in cases.items():
        ref = with_chosen_step(storage, T0)
        say(storage, ref, texts[name], back, facil, rec)
        person = turn_no(storage, ref, back, 4)  # #3 is the question
        assert (person.role, person.text) == ("user", texts[name]), name
        # without the question: a turn in the same session, recognize raising
        later = back + H
        if facil.answer is None:
            again(storage, ref, later, recognize=Rec(fail=RuntimeError("again")))
        say(storage, ref, texts[name] + " (ще)", later + M, Facil(), Rec(fail=RuntimeError("later")))
        mine = [x.text for x in turns(storage, ref, later + M) if x.role == "user"]
        assert mine[-2:] == [texts[name], texts[name] + " (ще)"], (name, mine)


def test_I3_clearer_never_reaches_the_analyzer(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    back = T0 + DAY
    plans = [
        Rec(outcome("worked", "yes", "двоє готові платити")),
        Rec(outcome("not_worked", "partly", "один відмовився")),
        Rec(outcome("unexpected", "no", "просять доставку")),
        Rec(outcome(None, "yes", "розповіла про зустріч")),
        Rec(outcome("worked", None, "все вдалося")),
        Rec(SKIPPED),
    ]
    for i, rec in enumerate(plans):
        ref = with_chosen_step(storage, T0, step_id=f"s{i}", step=f"Крок номер {i}")
        say(storage, ref, f"Ось як було {i}.", back, recognize=rec)
    llm = ScenarioLlm(answer=one_observation)
    analyze(storage, llm, back + H)
    assert len(llm.calls) == len(plans)
    whole = "\n".join(c.text for c in llm.calls)
    assert whole.count("[Результат кроку") == 4  # the four records with an outcome
    for value in ("yes", "partly", "no", "clearer"):
        assert not re.search(rf"\b{value}\b", whole, re.IGNORECASE), value
    for key in ("clearer_yes", "clearer_partly", "clearer_no"):
        label = uk(key)
        assert not re.search(rf"(?<!\w){re.escape(label)}(?!\w)", whole, re.IGNORECASE), (key, label)
