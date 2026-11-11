"""Contract tests of research-deep, the generators: `respond` under the router with `deep_question` (Seam 1:
the deep events and the card's end before the held update), with `deep_question: null` (Seam 4: the events
of S1), the retry of the update with the field, and `converse` on `answer` with `deep_question` (Seam 2)
(slice tester; from the contract).

Superseded by deep-research-confirm-first in part: a `deep_question` no longer runs the cycle in the same
reply — `with_deep` (under the router) and `deep_offer` (the router's `answer`) show a proposal instead."""

from typing import Any

from rdp_fakes import (
    DQ,
    INTRO,
    PROPOSAL_ABC,
    QA,
    QB,
    QC,
    Stream,
    card_answer,
    card_update,
    deep_llm,
    fa,
    fact_update,
    full_deep,
    plan_raw,
    rq,
    with_deep_question,
)

from thinkhow.facilitation import (
    FacilitatorUpdate,
    ReplyDelta,
    ResearchEvent,
    RoutingEvent,
    converse,
    respond,
)
from thinkhow.facilitation.respond import answer_schema, update_schema
from thinkhow.facilitation.types import DeepProposed, FactAnswer, Source
from thinkhow.platform import llm as pl

REPLY = "Звучить як питання ринку. Можу дослідити глибше."
DELTAS = ["Звучить як питання ринку. ", "Можу дослідити глибше."]
FOUND_1 = pl.Found(("Mittelstand Beratung",), (pl.Source("Перше джерело", "https://q.example/first"),), None)
LINE_1 = "\n\nДжерела: [Перше джерело](https://q.example/first)"
QUICK = ResearchEvent(
    depth="quick",
    queries=("Mittelstand Beratung",),
    sources=(Source("Перше джерело", "https://q.example/first"),),
    suggestions_html=None,
)


def texts(items: list[Any]) -> list[str]:
    return [i.text for i in items if isinstance(i, ReplyDelta)]


def offer_of(items: list[Any]) -> DeepProposed:
    (offer,) = [i for i in items if isinstance(i, DeepProposed)]
    return offer


def no_cycle(llm: Any) -> bool:
    return bool(llm.of("search") == [] and llm.of("report") == [])


def test_seam1_respond_under_the_router_gives_the_deep_events_and_the_card_end_before_the_held_update() -> (
    None
):
    first_fact = fact_update("d3-1", "Мета: перші гроші за пів року.", "t3")
    raw = card_answer(REPLY, "a_three", True, [first_fact], deep_question=DQ)
    llm = full_deep(streams=[Stream(list(DELTAS), raw, FOUND_1)])
    items: list[Any] = list(respond(rq.context(), rq.knowledge(), llm))
    update = items[-1]
    assert isinstance(update, FacilitatorUpdate)
    assert [i for i in items if isinstance(i, FacilitatorUpdate)] == [update]
    offer = offer_of(items)
    assert items.index(offer) < len(items) - 1
    assert (offer.pending.question, offer.pending.intro, list(offer.pending.questions)) == (
        DQ,
        INTRO,
        [QA, QB, QC],
    )
    ends = [i for i in items if isinstance(i, RoutingEvent)]
    assert [(e.decision.kind, e.decision.end, e.decision.card_id) for e in ends] == [("end", "done", "alpha")]
    assert items.index(ends[0]) < len(items) - 1
    assert QUICK in items
    assert not any(isinstance(i, ResearchEvent) and i.depth == "deep" for i in items)
    shown = "".join(texts(items))
    assert update.reply == shown
    assert shown.startswith(REPLY + LINE_1) and shown.endswith(PROPOSAL_ABC)
    assert shown[len(REPLY + LINE_1) : -len(PROPOSAL_ABC)].strip() == ""
    assert [u.model_dump() for u in update.map_updates] == [first_fact]
    assert (update.current_phase_id, update.phase_exit_met) == ("a_three", True)
    assert no_cycle(llm)


def test_seam4_routed_lead_with_deep_question_null_gives_the_events_of_s1_and_its_schema_has_the_field() -> (
    None
):
    llm = full_deep(streams=[Stream(list(DELTAS), card_answer(REPLY, "a_one", deep_question=None), FOUND_1)])
    items: list[Any] = list(respond(rq.context(), rq.knowledge(), llm))
    assert items == [
        ReplyDelta(DELTAS[0]),
        ReplyDelta(DELTAS[1]),
        ReplyDelta(LINE_1),
        QUICK,
        FacilitatorUpdate(
            reply=REPLY + LINE_1, current_phase_id="a_one", phase_exit_met=False, map_updates=[]
        ),
    ]
    (call,) = llm.calls
    assert call.kind == "stream"
    assert list(call.schema.model_fields) == [*answer_schema(rq.ALPHA).model_fields, "deep_question"]


def test_under_the_router_the_retry_of_the_update_carries_deep_question_and_the_proposal_follows() -> None:
    invalid = card_answer(REPLY, "b_one", deep_question=DQ)  # b_one is not a phase of alpha
    llm = full_deep(
        streams=[Stream(list(DELTAS), invalid, None)], updates=[card_update("a_two", deep_question=DQ)]
    )
    items: list[Any] = list(respond(rq.context(), rq.knowledge(), llm))
    (retry,) = llm.of("update")
    assert list(retry.schema.model_fields) == [*update_schema(rq.ALPHA).model_fields, "deep_question"]
    assert offer_of(items).pending.question == DQ
    update = items[-1]
    assert isinstance(update, FacilitatorUpdate)
    assert update.current_phase_id == "a_two"
    assert update.reply == "".join(texts(items))
    assert update.reply.startswith(REPLY) and update.reply.endswith(PROPOSAL_ABC)
    assert update.reply[len(REPLY) : -len(PROPOSAL_ABC)].strip() == ""
    assert no_cycle(llm)


def test_seam2_converse_on_answer_with_deep_question_shows_the_proposal_at_once_without_answer_fact() -> None:
    router = with_deep_question(fa.answer_raw(("alpha",)), DQ)
    llm = deep_llm(plans=[plan_raw()], router=[router])
    items: list[Any] = list(converse(fa.context((), turn_no=1, history=[]), fa.knowledge(), llm, fa.no_lead))
    assert type(items[0]).__name__ == "RoutingEvent"
    decision = items[0].decision
    assert (decision.kind, decision.card_id, decision.turn) == ("answer", None, 1)
    assert isinstance(items[-1], FacilitatorUpdate)
    middle = items[1:-1]
    assert {type(i).__name__ for i in middle} == {"ReplyDelta", "DeepProposed"}
    offer = offer_of(items)
    assert (offer.pending.question, offer.pending.intro, list(offer.pending.questions)) == (
        DQ,
        INTRO,
        [QA, QB, QC],
    )
    assert "".join(texts(items)) == PROPOSAL_ABC
    assert items[-1] == FacilitatorUpdate(
        reply=PROPOSAL_ABC, current_phase_id=None, phase_exit_met=False, map_updates=[]
    )
    assert fa.ROUTER_REPLY not in items[-1].reply
    assert llm.of("stream") == []
    assert all(c.schema is not FactAnswer for c in llm.calls)
    assert no_cycle(llm)
