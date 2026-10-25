"""The router before the facilitator (F5 without the experience path): who leads the reply, when a card ends.

Does NOT read steps.json or the experience memory, plan a route ahead or store anything (workspace does).
"""

from collections.abc import Callable, Iterator
from dataclasses import replace

from thinkhow.facilitation.answer import answer_fact
from thinkhow.facilitation.deep import deep_answer
from thinkhow.facilitation.route import RouterAnswer, route
from thinkhow.facilitation.types import (
    Decision,
    FacilitationContext,
    FacilitatorUpdate,
    ReplyDelta,
    ResearchEvent,
    Rev,
    RoutingEvent,
    current_card,
)
from thinkhow.knowledge import Card, CurrentKnowledge
from thinkhow.platform import llm as model

LeadItem = ReplyDelta | FacilitatorUpdate | ResearchEvent
Lead = Callable[[FacilitationContext, CurrentKnowledge, model.Llm], Iterator[LeadItem]]
DONE_WHY = "картку пройдено"
NOT_FIT_WHY = "картка не підходить"


def converse(
    ctx: FacilitationContext, knowledge: CurrentKnowledge, llm: model.Llm, lead: Lead
) -> Iterator[ReplyDelta | FacilitatorUpdate | RoutingEvent | ResearchEvent]:
    """Flow: route when no card is chosen → the chosen card's lead → the end of the card before the update."""
    routing = ctx.routing or ()
    card_id = current_card(routing)
    if card_id is None or card_id not in knowledge.cards:
        answer = route(ctx, knowledge, llm)
        decision = _decision(answer, ctx.turn_no, knowledge)
        yield RoutingEvent(decision)
        if answer.action == "answer" and answer.deep_question is not None:
            yield from deep_answer(answer.deep_question, ctx, llm, knowledge.rev_pair())
            return
        if answer.action == "answer":
            yield from answer_fact(ctx, knowledge, llm)
            return
        if answer.action != "choose":
            yield from _router_reply(answer)
            return
        routing = (*routing, decision)
        card_id = str(answer.card_id)
        ctx = replace(ctx, problem_map=ctx.problem_map.model_copy(update={"phase_id": None}))
    yield from _lead_card(replace(ctx, card_id=card_id, routing=routing), knowledge, llm, lead)


def _lead_card(
    ctx: FacilitationContext, knowledge: CurrentKnowledge, llm: model.Llm, lead: Lead
) -> Iterator[ReplyDelta | FacilitatorUpdate | RoutingEvent | ResearchEvent]:
    """The card's stream with its update held back, so the end of the card comes before it."""
    update: FacilitatorUpdate | None = None
    for item in lead(ctx, knowledge, llm):
        if isinstance(item, FacilitatorUpdate):
            update = item
            break
        yield item
    if update is None:
        return
    end = _end(knowledge.cards[ctx.card_id], update)
    if end is not None:
        why = DONE_WHY if end == "done" else NOT_FIT_WHY
        yield RoutingEvent(_end_decision(ctx, knowledge, end, why))
    yield update


def _end(card: Card, update: FacilitatorUpdate) -> str | None:
    if update.current_phase_id is None:
        return "not_fit"
    if update.current_phase_id == card.facilitator.phases[-1].id and update.phase_exit_met:
        return "done"
    return None


def _router_reply(answer: RouterAnswer) -> Iterator[ReplyDelta | FacilitatorUpdate]:
    text = str(answer.reply)
    yield ReplyDelta(text)
    yield FacilitatorUpdate(reply=text, current_phase_id=None, phase_exit_met=False, map_updates=[])


def _decision(answer: RouterAnswer, turn: int, knowledge: CurrentKnowledge) -> Decision:
    return Decision(
        turn=turn,
        rev=_rev(knowledge),
        kind=answer.action,
        profile=answer.profile,
        candidates=list(answer.candidates),
        card_id=answer.card_id if answer.action == "choose" else None,
        end=None,
        why=answer.why,
    )


def _end_decision(ctx: FacilitationContext, knowledge: CurrentKnowledge, end: str, why: str) -> Decision:
    return Decision.model_validate(
        {
            "turn": ctx.turn_no,
            "rev": _rev(knowledge).model_dump(),
            "kind": "end",
            "profile": None,
            "candidates": [],
            "card_id": ctx.card_id,
            "end": end,
            "why": why,
        }
    )


def _rev(knowledge: CurrentKnowledge) -> Rev:
    return Rev(rev=knowledge.rev, n=knowledge.n)
