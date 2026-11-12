"""Contract tests of deep-change-question: `propose`, `deep_changed`, `deep_offer`, `with_deep` of
`facilitation/deep.py` — the refined research question on a change, the fallback, the first proposal
untouched (hardest seams 2 and 3) (slice tester; from the contract «Seam», not the code; values by hand)."""

from typing import Any

from dcq_fakes import CHANGE, DQ, DQ2, PROPOSAL_2_DQ2, dc, plan_with

from thinkhow.facilitation import deep
from thinkhow.facilitation.types import FacilitatorUpdate, ReplyDelta


def proposed(items: list[Any]) -> list[Any]:
    return [i for i in items if type(i).__name__ == "DeepProposed"]


def shown(items: list[Any]) -> str:
    return "".join(i.text for i in items if isinstance(i, ReplyDelta))


def fields(p: Any) -> tuple[str, str, list[str]]:
    return p.question, p.intro, list(p.questions)


def changed_with(raw: str, previous: str = DQ) -> tuple[list[Any], Any]:
    llm = dc.DcLlm(plans=[raw])
    items = list(
        deep.deep_changed(dc.pending(previous, dc.INTRO_1, dc.PLAN_1), dc.context(text=CHANGE), llm, dc.REV)
    )
    return items, llm


def card_items() -> list[Any]:
    return [
        ReplyDelta(text=dc.CARD_REPLY),
        FacilitatorUpdate(
            reply=dc.CARD_REPLY, current_phase_id="a_one", phase_exit_met=False, map_updates=[]
        ),
    ]


def test_deep_changed_proposes_the_plans_refined_question_and_shows_it_with_one_plan_call() -> None:
    items, llm = changed_with(plan_with(dc.INTRO_2, dc.PLAN_2, DQ2))
    (event,) = proposed(items)
    assert fields(event.pending) == (DQ2, dc.INTRO_2, [dc.QD, dc.QE])
    assert shown(items) == PROPOSAL_2_DQ2
    assert [c.kind for c in llm.calls] == ["plan"]


def test_seam2_on_a_change_a_missing_null_empty_or_blank_plan_question_keeps_the_previous_one() -> None:
    items, _ = changed_with(plan_with(dc.INTRO_2, dc.PLAN_2, "  " + DQ2 + "  "))
    assert fields(proposed(items)[0].pending) == (DQ2, dc.INTRO_2, [dc.QD, dc.QE])
    for raw in (
        plan_with(dc.INTRO_2, dc.PLAN_2),
        plan_with(dc.INTRO_2, dc.PLAN_2, None),
        plan_with(dc.INTRO_2, dc.PLAN_2, ""),
        plan_with(dc.INTRO_2, dc.PLAN_2, "   "),
    ):
        items, llm = changed_with(raw)
        assert fields(proposed(items)[0].pending) == (DQ, dc.INTRO_2, [dc.QD, dc.QE]), raw
        assert shown(items) == dc.PROPOSAL_2, raw
        assert [c.kind for c in llm.calls] == ["plan"], raw


def test_propose_takes_the_plans_question_only_when_changed() -> None:
    propose = dc.api(deep, "propose")
    plain = dc.DcLlm(plans=[plan_with(dc.INTRO_2, dc.PLAN_2, DQ2)])
    got = propose(DQ, dc.context(), plain, dc.REV, False)
    assert fields(got) == (DQ, dc.INTRO_2, [dc.QD, dc.QE])
    on_change = dc.DcLlm(plans=[plan_with(dc.INTRO_2, dc.PLAN_2, DQ2)])
    got = propose(DQ, dc.context(text=CHANGE), on_change, dc.REV, False, changed=True)
    assert fields(got) == (DQ2, dc.INTRO_2, [dc.QD, dc.QE])
    assert len(on_change.of("plan")) == 1 and len(plain.of("plan")) == 1


def test_seam3_the_first_proposal_keeps_the_routers_or_facilitators_question_whatever_the_plan_says() -> None:
    offer = dc.DcLlm(plans=[plan_with(dc.INTRO_1, dc.PLAN_1, DQ2)])
    items: list[Any] = list(deep.deep_offer(DQ, dc.context(), offer, dc.REV))
    assert fields(proposed(items)[0].pending) == (DQ, dc.INTRO_1, [dc.QA, dc.QB, dc.QC])
    assert shown(items) == dc.PROPOSAL_1
    card = dc.DcLlm(plans=[plan_with(dc.INTRO_1, dc.PLAN_1, DQ2)])
    items = list(deep.with_deep(iter(card_items()), lambda: DQ, dc.context(), card, dc.REV))
    assert fields(proposed(items)[0].pending) == (DQ, dc.INTRO_1, [dc.QA, dc.QB, dc.QC])
    assert shown(items).endswith(dc.PROPOSAL_1)
