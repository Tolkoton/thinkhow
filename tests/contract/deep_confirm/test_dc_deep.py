"""Contract tests of deep-research-confirm-first: the functions of `facilitation/deep.py` — `propose`,
`proposal_text`, `run_deep`, `consent`, `with_deep`, `deep_offer`, `deep_agreed`, `deep_changed`
(slice tester; from the contract «Seam», not the code; expected values written by hand)."""

from collections import Counter
from typing import Any

import pytest
from dc_fakes import (
    CARD_REPLY,
    CHANGE,
    DQ,
    FACT_1,
    FACT_2,
    FIRST_REPLY_LINE,
    INTRO_1,
    INTRO_2,
    INVALID_PLAN,
    PLAN_1,
    PLAN_2,
    PLAN_4,
    PLAN_RAW_1,
    PLAN_RAW_2,
    PROPOSAL_1,
    PROPOSAL_2,
    PROPOSAL_4,
    QA,
    QB,
    QC,
    QD,
    QE,
    QF,
    QG,
    QH,
    QI,
    QUESTION_HEAD,
    REPORT,
    REPORT_RAW,
    REV,
    SEARCHES,
    SOURCES_LINE_1,
    STEPS_1,
    STEPS_4,
    DcLlm,
    api,
    consent_raw,
    context,
    is_report,
    pending,
)

from thinkhow.facilitation import deep
from thinkhow.facilitation.deep import DeepDone
from thinkhow.facilitation.types import (
    FacilitationError,
    FacilitatorUpdate,
    MapUpdate,
    ReplyDelta,
    ResearchEvent,
    Turn,
)
from thinkhow.platform import llm as pl

DOWN = pl.LlmUnavailable("search down")
NO_HISTORY: list[Turn] = []


def shown(items: list[Any]) -> str:
    return "".join(i.text for i in items if isinstance(i, ReplyDelta))


def proposed(items: list[Any]) -> list[Any]:
    return [i for i in items if type(i).__name__ == "DeepProposed"]


def updates(items: list[Any]) -> list[FacilitatorUpdate]:
    return [i for i in items if isinstance(i, FacilitatorUpdate)]


def fields(p: Any) -> tuple[str, str, list[str]]:
    return p.question, p.intro, list(p.questions)


# ------------------------------------------------------------------ propose


def test_propose_makes_one_plan_call_with_the_question_appended_and_returns_the_pending_without_search() -> (
    None
):
    llm = DcLlm(plans=[PLAN_RAW_1])
    got = api(deep, "propose")(DQ, context(), llm, REV, False)
    assert fields(got) == (DQ, INTRO_1, [QA, QB, QC])
    assert len(llm.of("plan")) == 1 and llm.of("search") == [] and llm.of("report") == []
    call = llm.of("plan")[0]
    assert call.system.startswith(deep.RULES["План"])
    assert call.contents[-1].text.endswith(QUESTION_HEAD + DQ)


def test_propose_puts_the_first_reply_line_into_the_plan_frame_only_when_first() -> None:
    first = DcLlm(plans=[PLAN_RAW_1])
    api(deep, "propose")(DQ, context(history=NO_HISTORY, turn_no=1), first, REV, True)
    assert FIRST_REPLY_LINE + "\n\n" in first.of("plan")[0].text
    other = DcLlm(plans=[PLAN_RAW_1])
    api(deep, "propose")(DQ, context(history=NO_HISTORY, turn_no=1), other, REV, False)
    assert FIRST_REPLY_LINE not in other.of("plan")[0].text
    assert FIRST_REPLY_LINE not in other.of("plan")[0].system


def test_propose_retries_an_invalid_plan_once_then_raises_facilitation_error() -> None:
    once = DcLlm(plans=[INVALID_PLAN, PLAN_RAW_2])
    assert fields(api(deep, "propose")(DQ, context(), once, REV, False)) == (DQ, INTRO_2, [QD, QE])
    assert len(once.of("plan")) == 2
    twice = DcLlm(plans=[INVALID_PLAN, INVALID_PLAN])
    with pytest.raises(FacilitationError):
        api(deep, "propose")(DQ, context(), twice, REV, False)
    assert len(twice.of("plan")) == 2


# ------------------------------------------------------------------ proposal_text


def test_proposal_text_is_intro_blank_line_question_and_one_dash_line_per_sub_question() -> None:
    text = api(deep, "proposal_text")
    assert text(pending(DQ, INTRO_1, PLAN_1)) == PROPOSAL_1
    assert text(pending(DQ, INTRO_2, PLAN_2)) == PROPOSAL_2
    assert text(
        pending(
            DQ, "Дослідю чотири боки ринку консалтингу — близько двох хвилин. Запускати чи змінити?", PLAN_4
        )
    ) == (PROPOSAL_4)


# ------------------------------------------------------------------ run_deep


def test_run_deep_shows_the_steps_searches_exactly_the_pending_questions_reports_and_never_plans() -> None:
    llm = DcLlm(reports=[REPORT_RAW])
    items = list(api(deep, "run_deep")(pending(DQ, INTRO_1, PLAN_1), context(), llm, REV))
    deltas = [i.text for i in items if isinstance(i, ReplyDelta)]
    assert deltas[0] == STEPS_1
    assert is_report(shown(items), STEPS_1, REPORT + SOURCES_LINE_1)
    assert Counter(llm.prompts()) == Counter([QA, QB, QC])
    assert llm.of("plan") == []
    assert len(llm.of("report")) == 1
    report_frame = llm.of("report")[0].text
    assert "[Питання людини]" in report_frame and DQ in report_frame
    assert isinstance(items[-1], DeepDone)
    assert items[-1].text == shown(items)


def test_run_deep_skips_a_failed_search_and_keeps_the_order_of_the_steps() -> None:
    searches: dict[str, Any] = dict(SEARCHES) | {QG: DOWN}
    llm = DcLlm(reports=[REPORT_RAW], searches=searches)
    items = list(api(deep, "run_deep")(pending(DQ, "Вступ.", PLAN_4), context(), llm, REV))
    assert [i.text for i in items if isinstance(i, ReplyDelta)][0] == STEPS_4
    assert Counter(llm.prompts()) == Counter([QF, QG, QH, QI])
    assert llm.of("plan") == []
    assert shown(items).endswith(
        "\n\nДжерела: [Förder F](https://f.example/f), [Kunden H](https://h.example/h), [Solo I](https://i.example/i)"
    )
    assert isinstance(items[-1], DeepDone)


def test_run_deep_with_every_search_failed_raises_llm_unavailable_without_a_report() -> None:
    llm = DcLlm(reports=[REPORT_RAW], searches={QD: DOWN, QE: DOWN})
    with pytest.raises(pl.LlmUnavailable):
        list(api(deep, "run_deep")(pending(DQ, INTRO_2, PLAN_2), context(), llm, REV))
    assert Counter(llm.prompts()) == Counter([QD, QE])
    assert llm.of("report") == [] and llm.of("plan") == []


# ------------------------------------------------------------------ consent


def test_consent_returns_the_answer_of_one_deep_consent_call() -> None:
    for word in ("yes", "change", "no", "other"):
        llm = DcLlm(consents=[consent_raw(word)])
        assert api(deep, "consent")(context(text="Так, давай."), llm, REV) == word
        assert len(llm.of("consent")) == 1
        assert llm.of("consent")[0].system.startswith(deep.RULES["Згода"])


def test_consent_retries_an_invalid_answer_once_then_raises_facilitation_error() -> None:
    once = DcLlm(consents=['{"answer": "maybe"}', consent_raw("no")])
    assert api(deep, "consent")(context(text="Ні."), once, REV) == "no"
    twice = DcLlm(consents=['{"answer": "maybe"}', "{}"])
    with pytest.raises(FacilitationError):
        api(deep, "consent")(context(text="Ні."), twice, REV)
    assert len(twice.of("consent")) == 2


# ------------------------------------------------------------------ with_deep


GOAL_UPDATE = MapUpdate(op="add", id="i2", type="goal", text="знайти перших клієнтів", turn="t3")


def card_items() -> list[Any]:
    return [
        ReplyDelta(text=CARD_REPLY),
        FacilitatorUpdate(
            reply=CARD_REPLY, current_phase_id="a_one", phase_exit_met=True, map_updates=[GOAL_UPDATE]
        ),
    ]


def test_with_deep_appends_the_proposal_instead_of_the_cycle_and_keeps_the_rest_of_the_update() -> None:
    llm = DcLlm(plans=[PLAN_RAW_1])
    items = list(deep.with_deep(iter(card_items()), lambda: DQ, context(), llm, REV))
    text = shown(items)
    assert text.startswith(CARD_REPLY) and text.endswith(PROPOSAL_1)
    assert text[len(CARD_REPLY) : -len(PROPOSAL_1)].strip() == ""
    assert len(proposed(items)) == 1 and fields(proposed(items)[0].pending) == (DQ, INTRO_1, [QA, QB, QC])
    (update,) = updates(items)
    assert items.index(proposed(items)[0]) < items.index(update)
    assert update.reply == text
    assert (update.current_phase_id, update.phase_exit_met, update.map_updates) == (
        "a_one",
        True,
        [GOAL_UPDATE],
    )
    assert llm.of("search") == [] and llm.of("report") == []
    assert FIRST_REPLY_LINE not in llm.of("plan")[0].text


def test_with_deep_under_deep_off_ignores_the_question() -> None:
    llm = DcLlm()
    items = list(deep.with_deep(iter(card_items()), lambda: DQ, context(deep_off=True), llm, REV))
    assert shown(items) == CARD_REPLY
    assert proposed(items) == []
    (update,) = updates(items)
    assert update == card_items()[1]
    assert llm.calls == []


# ------------------------------------------------------------------ deep_offer, deep_agreed, deep_changed


def test_deep_offer_shows_the_proposal_and_yields_the_event_and_an_update_without_phase_or_map() -> None:
    llm = DcLlm(plans=[PLAN_RAW_1])
    items = list(api(deep, "deep_offer")(DQ, context(history=NO_HISTORY, turn_no=1), llm, REV))
    assert shown(items) == PROPOSAL_1
    assert len(proposed(items)) == 1 and fields(proposed(items)[0].pending) == (DQ, INTRO_1, [QA, QB, QC])
    (update,) = updates(items)
    assert items.index(proposed(items)[0]) < items.index(update)
    assert update == FacilitatorUpdate(
        reply=PROPOSAL_1, current_phase_id=None, phase_exit_met=False, map_updates=[]
    )
    assert llm.of("search") == [] and llm.of("report") == []
    assert FIRST_REPLY_LINE in llm.of("plan")[0].text
    later = DcLlm(plans=[PLAN_RAW_1])
    list(api(deep, "deep_offer")(DQ, context(), later, REV))
    assert FIRST_REPLY_LINE not in later.of("plan")[0].text


def test_deep_agreed_runs_the_shown_plan_and_yields_the_deep_event_and_an_update_keeping_the_phase() -> None:
    llm = DcLlm(reports=[REPORT_RAW])
    items = list(api(deep, "deep_agreed")(pending(DQ, INTRO_1, PLAN_1), context(phase="a_two"), llm, REV))
    text = shown(items)
    assert is_report(text, STEPS_1, REPORT + SOURCES_LINE_1)
    assert llm.of("plan") == [] and Counter(llm.prompts()) == Counter([QA, QB, QC])
    events = [i for i in items if isinstance(i, ResearchEvent)]
    assert len(events) == 1
    assert (events[0].depth, events[0].question, events[0].report) == ("deep", DQ, REPORT)
    (update,) = updates(items)
    assert update.reply == text
    assert (update.current_phase_id, update.phase_exit_met) == ("a_two", False)
    assert sorted((u.type, u.text) for u in update.map_updates) == [("fact", FACT_1), ("fact", FACT_2)]
    assert proposed(items) == []


def test_deep_changed_proposes_again_for_the_same_question_with_the_change_in_the_frame() -> None:
    llm = DcLlm(plans=[PLAN_RAW_2])
    ctx = context(text=CHANGE, phase="a_two", history=NO_HISTORY, turn_no=1)
    items = list(api(deep, "deep_changed")(pending(DQ, INTRO_1, PLAN_1), ctx, llm, REV))
    assert shown(items) == PROPOSAL_2
    assert len(proposed(items)) == 1 and fields(proposed(items)[0].pending) == (DQ, INTRO_2, [QD, QE])
    (update,) = updates(items)
    assert update == FacilitatorUpdate(
        reply=PROPOSAL_2, current_phase_id="a_two", phase_exit_met=False, map_updates=[]
    )
    frame = llm.of("plan")[0]
    assert CHANGE in frame.text and frame.contents[-1].text.endswith(QUESTION_HEAD + DQ)
    assert FIRST_REPLY_LINE not in frame.text
    assert llm.of("search") == [] and llm.of("report") == []


def test_deep_research_and_deep_answer_are_gone_from_deep() -> None:
    assert not hasattr(deep, "deep_research")
    assert not hasattr(deep, "deep_answer")
