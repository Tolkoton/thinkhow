"""Contract tests of one-conversation: the facilitator's history is the whole topic (Seams 1, 2, 3, 5, 6, I1).

Slice tester; from the contract `.engine/slices/one-conversation.md`, not the code.
"""

from functools import partial
from pathlib import Path

import pytest
from oc_fakes import Fac, T, again, ask_reply, ca, rt, rtc, stp

from thinkhow.facilitation import respond
from thinkhow.knowledge import CurrentKnowledge
from thinkhow.platform.storage import LocalStorage
from thinkhow.workspace import Answered, Failed, NothingToRetry

ALICE = ca.ALICE
DAY, H, M = ca.DAY, ca.H, ca.M
FIRST_REPLY = "Перша відповідь у темі"


@pytest.fixture
def logs(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> ca.LogCapture:
    return ca.install_log_capture(monkeypatch, capsys)


# --- Seam 1: the turn that opens a new session -----------------------------------------------------


def test_seam1_the_turn_after_24h_of_silence_gets_every_turn_of_the_first_session(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    t0 = ca.NOW - 3 * DAY
    ref = ca.new_topic(storage, ALICE, t0 - M)
    fac = Fac(["Що може піти не так?", "Що змінилось?"])
    ask_reply(storage, fac, ALICE, ref, "Хочу відкрити кав'ярню.", t0)
    got = ask_reply(storage, fac, ALICE, ref, "Повернувся через добу.", t0 + DAY)
    assert got[-1] == Answered(4)
    assert len(fac.contexts) == 2
    assert fac.contexts[1].turn_no == 3
    assert fac.contexts[1].history == [
        T("user", "Хочу відкрити кав'ярню."),
        T("model", "Що може піти не так?"),
    ]


# --- Seam 2: the return with the step question (S6) ------------------------------------------------


def test_seam2_after_the_step_question_the_history_is_the_first_session_and_the_question_in_order(
    tmp_path: Path,
) -> None:
    storage = LocalStorage(tmp_path)
    t0 = stp.T0
    ref = stp.with_chosen_step(storage, t0)  # #1 user «Хочу відкрити кав'ярню.», #2 model writes the step
    stp.say(storage, ref, "Ще одна думка.", t0 + H, stp.Facil(answer="Що саме?"))  # #3, #4: same session
    back = t0 + H + DAY
    shown = stp.question_now(storage, ref, back)
    assert shown is not None
    fac = Fac(["Чудово. Хто третій?"])
    got = ask_reply(storage, fac, ALICE, ref, "Вийшло: двоє готові платити.", back, question=stp.Q)
    assert got[-1] == Answered(7)  # #5 the question, #6 the person, #7 the answer
    (ctx,) = fac.contexts
    assert ctx.turn_no == 6
    assert ctx.history == [
        T("user", "Хочу відкрити кав'ярню."),
        T("model", "Добре. Що далі?"),
        T("user", "Ще одна думка."),
        T("model", "Що саме?"),
        T("model", shown),
    ]


# --- Seam 3: retry in a new session ----------------------------------------------------------------


def test_seam3_retry_in_a_new_session_gets_the_whole_topic_without_a_second_copy_of_the_turn(
    tmp_path: Path,
) -> None:
    storage = LocalStorage(tmp_path)
    t0 = ca.NOW - 3 * DAY
    ref = ca.new_topic(storage, ALICE, t0 - M)
    fac = Fac(["Два?", "Чотири?", None, "Шість?"])
    ask_reply(storage, fac, ALICE, ref, "Один.", t0)
    back = t0 + DAY
    ask_reply(storage, fac, ALICE, ref, "Три.", back)
    failed = ask_reply(storage, fac, ALICE, ref, "П'ять.", back + M)
    assert isinstance(failed[-1], Failed)
    got = again(storage, fac, ALICE, ref, back + 2 * M)
    assert got[-1] == Answered(6)
    assert len(fac.contexts) == 4
    retried = fac.contexts[3]
    assert retried.turn_no == 5
    assert retried.text == "П'ять."
    assert retried.history == [
        T("user", "Один."),
        T("model", "Два?"),
        T("user", "Три."),
        T("model", "Чотири?"),
    ]


# --- Seam 5: FIRST_REPLY_LINE (Q4) -----------------------------------------------------------------


def _knowledge() -> CurrentKnowledge:
    return rt.knowledge(cards=(rtc.ALPHA, rtc.BETA, rtc.GAMMA, rtc.PREMORTEM))


def test_seam5_the_first_reply_line_is_on_the_topics_first_reply_and_not_on_a_new_sessions(
    tmp_path: Path,
) -> None:
    storage = LocalStorage(tmp_path)
    t0 = ca.NOW - 3 * DAY

    # the topic's first reply: the router chooses a card on turn 1 → the frame carries the line
    first = ca.new_topic(storage, ALICE, t0 - M, "Перша")
    llm1 = rt.RouterLlm(
        generate=[rt.choose("alpha")], streams=[rt.fac_answer("Схоже, що … Що головне?", "a_one")]
    )
    got = ask_reply(storage, partial(respond, knowledge=_knowledge(), llm=llm1), ALICE, first, "Не знаю.", t0)
    assert isinstance(got[-1], Answered)
    assert len(llm1.stream_calls) == 1
    assert FIRST_REPLY in llm1.stream_calls[0].frame

    # a new session without the S6 question; the router chooses a card on that same turn
    later = ca.new_topic(storage, ALICE, t0 - M, "Друга")
    llm2 = rt.RouterLlm(
        generate=[rt.ask(), rt.choose("alpha")],
        streams=[rt.fac_answer("Схоже, що … Що головне?", "a_one")],
    )
    fac2 = partial(respond, knowledge=_knowledge(), llm=llm2)
    got = ask_reply(storage, fac2, ALICE, later, "Хочу подумати.", t0)
    assert isinstance(got[-1], Answered)
    assert llm2.stream_calls == []
    got = ask_reply(storage, fac2, ALICE, later, "Про кав'ярню.", t0 + DAY)
    assert isinstance(got[-1], Answered)
    assert len(llm2.router_calls) == 2
    assert len(llm2.stream_calls) == 1
    assert FIRST_REPLY not in llm2.stream_calls[0].frame


# --- Seam 6: reply_failed --------------------------------------------------------------------------


def test_seam6_a_failed_answer_logs_one_reply_failed_line_with_the_whole_history_length(
    tmp_path: Path, logs: ca.LogCapture
) -> None:
    storage = LocalStorage(tmp_path)
    t0 = ca.NOW - 3 * DAY
    ref = ca.new_topic(storage, ALICE, t0 - M)
    fac = Fac(["Два?", "Чотири?", "Шість?", None])
    ask_reply(storage, fac, ALICE, ref, "Один.", t0)
    ask_reply(storage, fac, ALICE, ref, "Три.", t0 + H)
    ask_reply(storage, fac, ALICE, ref, "П'ять.", t0 + H + DAY)  # a new session
    assert logs.events("reply_failed") == []  # successful answers: no line
    got = ask_reply(storage, fac, ALICE, ref, "Сім.", t0 + H + DAY + M)
    failed = got[-1]
    assert isinstance(failed, Failed)
    lines = logs.events("reply_failed")
    assert len(lines) == 1
    (line,) = lines
    assert line["severity"] == "WARNING"
    assert line["uid"] == ALICE.id
    assert line["topic_id"] == ref.topic_id
    assert "turn" in line
    assert line["reason"] == failed.reason
    assert line["history_turns"] == 6


# --- I1 --------------------------------------------------------------------------------------------


def test_I1_the_history_of_turn_n_is_every_turn_numbered_below_n_whatever_the_sessions(
    tmp_path: Path,
) -> None:
    storage = LocalStorage(tmp_path)
    t0 = ca.NOW - 10 * DAY

    # the first turn of a topic: n = 1, nothing below it
    a = ca.new_topic(storage, ALICE, t0 - M, "А")
    fac = Fac(["Так?"])
    ask_reply(storage, fac, ALICE, a, "Перша.", t0)
    assert fac.contexts[0].turn_no == 1 and fac.contexts[0].history == []

    # an unanswered turn left in a session closed by silence; the next turn opens a new one
    b = ca.new_topic(storage, ALICE, t0 - M, "Б")
    fac = Fac([None, "Ну?"])
    ask_reply(storage, fac, ALICE, b, "Без відповіді.", t0)
    with pytest.raises(NothingToRetry):
        again(storage, fac, ALICE, b, t0 + DAY)  # refused: the session is closed
    ask_reply(storage, fac, ALICE, b, "Знову я.", t0 + DAY)
    assert fac.contexts[1].turn_no == 2
    assert fac.contexts[1].history == [T("user", "Без відповіді.")]

    # a legacy topic: session 1 closed by the old `closed` marker, session 2 after it
    old = ca.NOW - 8 * DAY
    c = ca.legacy_topic(
        storage,
        ALICE,
        [
            ca.LS(1, ca.pair(1, "в-перша", old), closed=old + H),
            ca.LS(2, ca.pair(3, "в-друга", old + 2 * DAY)),
        ],
    )
    fac = Fac(["П'ятий?"])
    ask_reply(storage, fac, ALICE, c, "Повертаюсь.", ca.NOW - H)
    assert fac.contexts[0].turn_no == 5
    assert fac.contexts[0].history == [
        T("user", "в-перша людина 1"),
        T("model", "в-перша фасилітатор 2"),
        T("user", "в-друга людина 3"),
        T("model", "в-друга фасилітатор 4"),
    ]

    # three sessions; in the third a failed reply, its retry, then one more turn in the same session
    d = ca.new_topic(storage, ALICE, t0 - M, "Г")
    fac = Fac(["Два?", "Чотири?", None, "Шість?", "Вісім?"])
    ask_reply(storage, fac, ALICE, d, "Один.", t0)
    ask_reply(storage, fac, ALICE, d, "Три.", t0 + DAY)
    third = t0 + 2 * DAY
    ask_reply(storage, fac, ALICE, d, "П'ять.", third)
    again(storage, fac, ALICE, d, third + M)
    ask_reply(storage, fac, ALICE, d, "Сім.", third + 2 * M)
    four = [T("user", "Один."), T("model", "Два?"), T("user", "Три."), T("model", "Чотири?")]
    assert [c.turn_no for c in fac.contexts] == [1, 3, 5, 5, 7]
    assert fac.contexts[2].history == four
    assert fac.contexts[3].history == four
    assert fac.contexts[4].history == [*four, T("user", "П'ять."), T("model", "Шість?")]
