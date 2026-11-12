"""Contract tests of deep-change-question: one test per invariant I1–I3 of the contract, inputs chosen by
hand from each rule's «Domain» (slice tester; from the contract, not the code; expected values by hand)."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

from dcq_fakes import CHANGE, CHANGE_AGAIN, DQ, DQ2, DQ3, dc, plan_with

from thinkhow.facilitation import deep
from thinkhow.facilitation.types import FacilitatorUpdate, ReplyDelta
from thinkhow.workspace import Answered

ABSENT: Any = object()


def raw(question: Any, four: bool = False) -> str:
    intro, questions = (dc.INTRO_4, dc.PLAN_4) if four else (dc.INTRO_2, dc.PLAN_2)
    return plan_with(intro, questions) if question is ABSENT else plan_with(intro, questions, question)


def the_question(items: list[Any]) -> str:
    (event,) = [i for i in items if type(i).__name__ == "DeepProposed"]
    question: str = event.pending.question
    return question


def test_I1_on_a_change_the_question_is_the_trimmed_plan_question_if_not_empty_else_the_previous_one() -> (
    None
):
    cases = [
        (DQ, ABSENT, DQ),
        (DQ, None, DQ),
        (DQ, "", DQ),
        (DQ, " \t\n ", DQ),
        (DQ, "  " + DQ2 + "  ", DQ2),
        (DQ, DQ, DQ),
        (DQ, DQ3, DQ3),
        (DQ2, ABSENT, DQ2),
        (DQ2, None, DQ2),
        (DQ2, "", DQ2),
        (DQ2, "   ", DQ2),
        (DQ2, "\n" + DQ3 + " ", DQ3),
        (DQ2, DQ2, DQ2),
        (DQ2, DQ, DQ),
    ]
    for previous, given, expected in cases:
        llm = dc.DcLlm(plans=[raw(given)])
        pending = dc.pending(previous, dc.INTRO_1, dc.PLAN_1)
        items = list(deep.deep_changed(pending, dc.context(text=CHANGE), llm, dc.REV))
        assert the_question(items) == expected, (previous, given)


def asking(question: str) -> Callable[[], str]:
    return lambda: question


def card_items() -> list[Any]:
    return [
        ReplyDelta(text=dc.CARD_REPLY),
        FacilitatorUpdate(
            reply=dc.CARD_REPLY, current_phase_id="a_one", phase_exit_met=False, map_updates=[]
        ),
    ]


def test_I2_the_first_proposal_keeps_the_given_question_whatever_the_plan_returns_in_question() -> None:
    for asked in (DQ, DQ3):
        for given in (ABSENT, None, "", "   ", DQ2, "  " + DQ2 + "  ", DQ, DQ3):
            first = dc.DcLlm(plans=[raw(given)])
            ctx = dc.context(history=[], turn_no=1)
            items: list[Any] = list(deep.deep_offer(asked, ctx, first, dc.REV))
            assert the_question(items) == asked, ("deep_offer first", asked, given)
            later = dc.DcLlm(plans=[raw(given)])
            items = list(deep.deep_offer(asked, dc.context(), later, dc.REV))
            assert the_question(items) == asked, ("deep_offer", asked, given)
            card = dc.DcLlm(plans=[raw(given)])
            items = list(deep.with_deep(iter(card_items()), asking(asked), dc.context(), card, dc.REV))
            assert the_question(items) == asked, ("with_deep", asked, given)


def _chain(root: Path, changes: list[Any]) -> tuple[str, str, str]:
    """Proposal on the router with DQ, then the changes (each a plan `question` or ABSENT), then «так».
    Returns the last shown proposal, the frame of the report call and the question of the research entry."""
    ref = dc.new_topic(root)
    dc.propose_on_router(root, ref)
    turn = 2
    last = dc.PROPOSAL_1
    for n, given in enumerate(changes):
        llm = dc.DcLlm(consents=[dc.consent_raw("change")], plans=[raw(given, four=n % 2 == 1)])
        got, last = dc.say(root, dc.fac(llm), ref, CHANGE if n % 2 == 0 else CHANGE_AGAIN)
        turn += 2
        assert got[-1] == Answered(turn), got[-1]
    yes = dc.agree_llm()
    got, _ = dc.say(root, dc.fac(yes), ref, "Так, запускай.")
    assert got[-1] == Answered(turn + 2), got[-1]
    entries = dc.rq.read_research(dc.store_at(root), ref)
    assert entries is not None and len(entries) == 1
    return last, yes.of("report")[0].text, str(entries[0]["question"])


def test_I3_after_yes_the_report_and_its_event_use_the_question_of_the_last_shown_proposal(
    tmp_path: Path,
) -> None:
    chains: list[tuple[list[Any], str]] = [
        ([], DQ),
        ([DQ2], DQ2),
        ([None], DQ),
        (["   "], DQ),
        ([DQ2, ABSENT], DQ2),
        ([DQ2, "  " + DQ3 + "  "], DQ3),
        ([DQ2, DQ], DQ),
        ([ABSENT, DQ3, ""], DQ3),
    ]
    for i, (changes, expected) in enumerate(chains):
        last, frame, event_question = _chain(tmp_path / str(i), changes)
        assert "\n\n" + expected + "\n- " in last, (changes, last)
        assert "[Питання людини]\n" + expected in frame, changes
        assert event_question == expected, changes
