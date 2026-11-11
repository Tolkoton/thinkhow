"""Contract tests of deep-research-confirm-first: the invariants I1–I4, each on inputs chosen by hand from its
«Domain» (slice tester; expected values written by hand). Every answer reads the topic through a new storage
object on the same folder."""

from collections import Counter
from datetime import timedelta
from pathlib import Path
from typing import Any

from dc_fakes import (
    CARD_REPLY,
    CHANGE,
    DAY,
    DQ,
    FILE_1,
    FILE_2,
    FILE_4,
    PLAN_1,
    PLAN_2,
    PLAN_4,
    PLAN_RAW_1,
    PLAN_RAW_2,
    PLAN_RAW_4,
    PROPOSAL_1,
    PROPOSAL_2,
    PROPOSAL_4,
    QE,
    REPORT,
    SEARCHES,
    SOURCES_LINE_1,
    STEPS_1,
    STEPS_2,
    STEPS_4,
    T0,
    DcLlm,
    Down,
    Q,
    Scripted,
    Stream,
    again,
    agree_llm,
    card_raw,
    chosen_step,
    consent_raw,
    fa,
    fac,
    is_report,
    new_topic,
    pending_file,
    plain,
    propose_on_router,
    recorded,
    router_ask,
    router_deep,
    rq,
    say,
    store_at,
)

from thinkhow.platform import llm as pl
from thinkhow.workspace import Answered, Failed, TopicRef
from thinkhow.workspace.conversation import normalize

DOWN = pl.LlmUnavailable("search down")
M = timedelta(minutes=1)


def card_proposal(tmp_path: Path, ref: TopicRef, plan: str) -> None:
    llm = DcLlm(streams=[Stream([CARD_REPLY], card_raw(CARD_REPLY, "a_one", DQ))], plans=[plan])
    got, _ = say(tmp_path, fac(llm), ref, "Досліди ринок глибоко.")
    assert got[-1] == Answered(2), got[-1]


def research_raw(tmp_path: Path, ref: TopicRef) -> bytes | None:
    data: bytes | None = rq.raw_research(store_at(tmp_path), ref)
    return data


# ------------------------------------------------------------------ I1


def test_I1_after_yes_the_searches_are_exactly_the_shown_sub_questions_and_the_plan_is_not_called(
    tmp_path: Path,
) -> None:
    # (a) the router's path, three sub-questions, every search found
    a = tmp_path / "a"
    ref = new_topic(a)
    propose_on_router(a, ref)
    llm = agree_llm()
    got, shown = say(a, fac(llm), ref, "Так.")
    assert got[-1] == Answered(4), got[-1]
    assert Counter(llm.prompts()) == Counter(PLAN_1) and llm.of("plan") == []
    assert shown.startswith(STEPS_1 + "\n")

    # (b) under the card, two sub-questions, one search failed
    b = tmp_path / "b"
    ref = new_topic(b, "alpha")
    card_proposal(b, ref, PLAN_RAW_2)
    searches: dict[str, Any] = dict(SEARCHES) | {QE: DOWN}
    llm = agree_llm(searches=searches)
    got, shown = say(b, fac(llm), ref, "Давай.")
    assert got[-1] == Answered(4), got[-1]
    assert Counter(llm.prompts()) == Counter(PLAN_2) and llm.of("plan") == []
    assert shown.startswith(STEPS_2 + "\n")

    # (c) a change before yes: the new four sub-questions are searched, not the old three
    c = tmp_path / "c"
    ref = new_topic(c)
    propose_on_router(c, ref)
    got, _ = say(c, fac(DcLlm(consents=[consent_raw("change")], plans=[PLAN_RAW_4])), ref, CHANGE)
    assert got[-1] == Answered(4), got[-1]
    llm = agree_llm()
    got, shown = say(c, fac(llm), ref, "Запускай.")
    assert got[-1] == Answered(6), got[-1]
    assert Counter(llm.prompts()) == Counter(PLAN_4) and llm.of("plan") == []
    assert shown.startswith(STEPS_4 + "\n")

    # (d) «так» to the step question after a break (S6), in reply and in retry after a failure: no search
    for name, failed_first in (("d", False), ("e", True)):
        d = tmp_path / name
        ref = new_topic(d)
        got, _ = say(
            d, Scripted([plain("Добре. Що зробите першим кроком?", [chosen_step(2)])]), ref, "Шукаю клієнтів."
        )
        assert got[-1] == Answered(2), got[-1]
        propose_on_router(d, ref)
        llm = DcLlm(router=[router_ask()])
        if failed_first:
            got, _ = say(d, Scripted([[Down("model down")]]), ref, "Так.", T0 + DAY, question=Q)
            assert isinstance(got[-1], Failed), got[-1]
            got, _ = again(d, fac(llm), ref, T0 + DAY + M)
        else:
            got, _ = say(d, fac(llm), ref, "Так.", T0 + DAY, question=Q)
        assert got[-1] == Answered(7), got[-1]
        assert llm.prompts() == [] and llm.of("consent") == []


# ------------------------------------------------------------------ I2


def test_I2_the_answer_that_decides_to_research_deep_makes_no_search_and_writes_no_research(
    tmp_path: Path,
) -> None:
    # the router's «answer» with a deep_question
    a = tmp_path / "a"
    ref = new_topic(a)
    llm = propose_on_router(a, ref)
    assert llm.prompts() == [] and llm.of("report") == []
    assert research_raw(a, ref) is None

    # the facilitator under the card with a deep_question, after a quick search that wrote research.json
    b = tmp_path / "b"
    ref = new_topic(b, "alpha")
    quick = DcLlm(
        streams=[
            Stream(
                ["Оренда в центрі — від 30 євро за метр."],
                card_raw("Оренда в центрі — від 30 євро за метр."),
                fa.FOUND,
            )
        ]
    )
    got, _ = say(b, fac(quick), ref, "Скільки коштує оренда?")
    assert got[-1] == Answered(2), got[-1]
    before = research_raw(b, ref)
    assert before is not None
    llm = DcLlm(streams=[Stream([CARD_REPLY], card_raw(CARD_REPLY, "a_one", DQ))], plans=[PLAN_RAW_1])
    got, _ = say(b, fac(llm), ref, "Досліди ринок глибоко.")
    assert got[-1] == Answered(4), got[-1]
    assert llm.prompts() == [] and llm.of("report") == []
    assert research_raw(b, ref) == before

    # a change of the proposal
    c = tmp_path / "c"
    ref = new_topic(c)
    propose_on_router(c, ref)
    llm = DcLlm(consents=[consent_raw("change")], plans=[PLAN_RAW_2])
    got, _ = say(c, fac(llm), ref, CHANGE)
    assert got[-1] == Answered(4), got[-1]
    assert llm.prompts() == [] and llm.of("report") == []
    assert research_raw(c, ref) is None


# ------------------------------------------------------------------ I3


def test_I3_after_every_successful_answer_the_file_exists_iff_that_answer_proposed_and_holds_it(
    tmp_path: Path,
) -> None:
    ref = new_topic(tmp_path)

    def step(
        facilitate: Any, text: str, want_turn: int, want_file: Any, at: Any = T0, question: Any = None
    ) -> None:
        got, _ = say(tmp_path, facilitate, ref, text, at, question=question)
        assert got[-1] == Answered(want_turn), (text, got[-1])
        assert pending_file(tmp_path, ref) == want_file, text

    # an answer without research (it also writes a chosen step for later): no file
    step(Scripted([plain("Добре. Що зробите першим кроком?", [chosen_step(2)])]), "Шукаю клієнтів.", 2, None)
    # a proposal
    step(
        fac(DcLlm(router=[router_deep()], plans=[PLAN_RAW_1])),
        "Досліди глибоко.",
        4,
        {"turn": 4, "pending": FILE_1},
    )
    # a change: the new one, with the number of this answer
    step(
        fac(DcLlm(consents=[consent_raw("change")], plans=[PLAN_RAW_2])),
        CHANGE,
        6,
        {"turn": 6, "pending": FILE_2},
    )
    # something else: dropped
    step(fac(DcLlm(consents=[consent_raw("other")], router=[router_ask()])), "А про нішу?", 8, None)
    # a proposal again, then a failed answer leaves it, then retry with «no»: gone
    step(
        fac(DcLlm(router=[router_deep()], plans=[PLAN_RAW_4])),
        "Досліди глибше.",
        10,
        {"turn": 10, "pending": FILE_4},
    )
    got, _ = say(tmp_path, Scripted([[Down("model down")]]), ref, "Ні.")
    assert isinstance(got[-1], Failed)
    assert pending_file(tmp_path, ref) == {"turn": 10, "pending": FILE_4}
    no = DcLlm(
        consents=[consent_raw("no")], router=[router_deep()], streams=[Stream(list(fa.DELTAS), fa.fact_raw())]
    )
    got, _ = again(tmp_path, fac(no), ref)
    assert got[-1] == Answered(12), got[-1]
    assert pending_file(tmp_path, ref) is None
    # a proposal, then «yes»: gone
    step(
        fac(DcLlm(router=[router_deep()], plans=[PLAN_RAW_1])),
        "Досліди глибоко.",
        14,
        {"turn": 14, "pending": FILE_1},
    )
    step(fac(agree_llm()), "Так.", 16, None)
    # a proposal, a break with the step question before the person's «так»: gone, and no consent read
    step(
        fac(DcLlm(router=[router_deep()], plans=[PLAN_RAW_2])),
        "Досліди конкурентів.",
        18,
        {"turn": 18, "pending": FILE_2},
    )
    step(fac(DcLlm(router=[router_ask()])), "Так.", 21, None, T0 + DAY, Q)


# ------------------------------------------------------------------ I4


def test_I4_the_text_shown_equals_the_recorded_answer_on_every_path_of_the_slice(tmp_path: Path) -> None:
    # the proposal on the router's path
    a = tmp_path / "a"
    ref = new_topic(a)
    got, shown = say(a, fac(DcLlm(router=[router_deep()], plans=[PLAN_RAW_1])), ref, "Досліди глибоко.")
    assert got[-1] == Answered(2), got[-1]
    assert shown == PROPOSAL_1 and recorded(a, ref) == normalize(shown)

    # a change of it
    got, shown = say(a, fac(DcLlm(consents=[consent_raw("change")], plans=[PLAN_RAW_4])), ref, CHANGE)
    assert got[-1] == Answered(4), got[-1]
    assert shown == PROPOSAL_4 and recorded(a, ref) == normalize(shown)

    # the report after yes, with sources
    b = tmp_path / "b"
    ref = new_topic(b)
    propose_on_router(b, ref)
    got, shown = say(b, fac(agree_llm()), ref, "Так.")
    assert got[-1] == Answered(4), got[-1]
    assert is_report(shown, STEPS_1, REPORT + SOURCES_LINE_1) and recorded(b, ref) == normalize(shown)

    # the report after yes, without sources
    c = tmp_path / "c"
    ref = new_topic(c)
    propose_on_router(c, ref)
    bare: dict[str, Any] = {q: (SEARCHES[q][0], None) for q in PLAN_1}
    got, shown = say(c, fac(agree_llm(searches=bare)), ref, "Так.")
    assert got[-1] == Answered(4), got[-1]
    assert "Джерела: " not in shown
    assert shown.startswith(STEPS_1) and recorded(c, ref) == normalize(shown)

    # the proposal after the card's reply
    d = tmp_path / "d"
    ref = new_topic(d, "alpha")
    llm = DcLlm(streams=[Stream([CARD_REPLY], card_raw(CARD_REPLY, "a_one", DQ))], plans=[PLAN_RAW_2])
    got, shown = say(d, fac(llm), ref, "Досліди ринок глибоко.")
    assert got[-1] == Answered(2), got[-1]
    assert shown.startswith(CARD_REPLY) and shown.endswith(PROPOSAL_2)
    assert recorded(d, ref) == normalize(shown)
