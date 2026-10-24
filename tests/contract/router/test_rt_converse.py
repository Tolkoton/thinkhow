"""Contract tests of `converse`: who leads the reply, and the end of a card before the update (Seam 1)
(slice tester; from the contract, not the code)."""

from typing import Any

from rt_cards import ITEM, problem_map
from rt_fakes import (
    ASK_REPLY,
    OFFER_REPLY,
    PROFILE_OBJ,
    RecordingLead,
    RouterLlm,
    ask,
    choose,
    collect,
    context,
    d_ask,
    d_choose,
    d_end,
    d_offer,
    deltas,
    events,
    knowledge,
    led,
    offer,
    same_but_why,
    update,
    updates,
)

from thinkhow.facilitation import converse
from thinkhow.facilitation.types import (
    Candidate,
    FacilitationContext,
    FacilitatorUpdate,
    ReplyDelta,
    RoutingEvent,
)
from thinkhow.knowledge import CurrentKnowledge


def run(
    ctx: FacilitationContext, llm: RouterLlm, lead: RecordingLead, k: CurrentKnowledge | None = None
) -> list[Any]:
    items, err = collect(lambda: converse(ctx, knowledge() if k is None else k, llm, lead))
    assert err is None, err
    return items


def test_offer_with_no_decisions_is_one_routing_event_one_delta_and_a_null_update() -> None:
    llm, lead = RouterLlm(generate=[offer("beta", "gamma")]), RecordingLead()
    items = run(context((), turn_no=1), llm, lead)
    assert events(items) == [d_offer(1, "beta", "gamma")]
    assert deltas(items) == [ReplyDelta(text=OFFER_REPLY)]
    assert items[-1] == FacilitatorUpdate(
        reply=OFFER_REPLY, current_phase_id=None, phase_exit_met=False, map_updates=[]
    )
    assert len(updates(items)) == 1
    assert lead.contexts == []
    assert llm.stream_calls == []


def test_ask_is_one_routing_event_one_delta_and_a_null_update() -> None:
    llm, lead = RouterLlm(generate=[ask()]), RecordingLead()
    items = run(context((d_offer(1, "alpha", "beta"),), turn_no=3), llm, lead)
    assert events(items) == [d_ask(3)]
    assert deltas(items) == [ReplyDelta(text=ASK_REPLY)]
    assert items[-1] == FacilitatorUpdate(
        reply=ASK_REPLY, current_phase_id=None, phase_exit_met=False, map_updates=[]
    )
    assert lead.contexts == []


def test_decision_carries_the_turn_the_revision_the_profile_and_the_ranked_candidates() -> None:
    llm = RouterLlm(generate=[offer("gamma", "alpha", "beta", why="три способи")])
    items = run(context((), turn_no=7), llm, RecordingLead(), knowledge(rev=5, n=2))
    (decision,) = events(items)
    assert decision.turn == 7
    assert decision.rev.rev == 5 and decision.rev.n == 2
    assert decision.kind == "offer" and decision.end is None
    assert decision.profile == PROFILE_OBJ
    assert [c.card_id for c in decision.candidates] == ["gamma", "alpha", "beta"]
    assert all(isinstance(c, Candidate) for c in decision.candidates)
    assert decision.why == "три способи"


def test_choose_hands_the_chosen_card_to_lead_in_the_same_reply_from_its_first_phase() -> None:
    before = (d_offer(1, "beta", "gamma"),)
    llm = RouterLlm(generate=[choose("beta")])
    lead = RecordingLead([led("b_one")])
    ctx = context(before, card_id="pre-mortem", pm=problem_map("a_two", 2), turn_no=3)
    items = run(ctx, llm, lead)
    assert events(items) == [d_choose(3, "beta")]
    (got,) = lead.contexts
    assert got.card_id == "beta"
    assert got.routing == (*before, d_choose(3, "beta"))
    assert got.problem_map.phase_id is None
    assert got.problem_map.items == [ITEM]
    assert got.turn_no == 3 and got.text == ctx.text and got.history == ctx.history
    assert len(updates(items)) == 1 and items[-1] == update("b_one", reply="Що далі?")


def test_with_a_card_chosen_no_router_call_and_lead_gets_that_card_and_the_routing() -> None:
    routing = (d_offer(1, "alpha", "beta"), d_choose(3, "alpha"))
    llm, lead = RouterLlm(), RecordingLead([led("a_two")])
    ctx = context(routing, card_id="alpha", pm=problem_map("a_one", 4), turn_no=5)
    items = run(ctx, llm, lead)
    assert llm.router_calls == []
    (got,) = lead.contexts
    assert got.card_id == "alpha"
    assert got.routing == routing
    assert got.problem_map == problem_map("a_one", 4)
    assert events(items) == []


def test_lead_deltas_pass_on_in_order_and_its_update_closes_the_stream() -> None:
    routing = (d_choose(1, "alpha"),)
    lead = RecordingLead([led("a_two", deltas=("Раз ", "два ", "три?"))])
    items = run(context(routing, pm=problem_map("a_one", 2)), RouterLlm(), lead)
    assert deltas(items) == [ReplyDelta("Раз "), ReplyDelta("два "), ReplyDelta("три?")]
    assert items[-1] == update("a_two", reply="Раз два три?")


def test_seam1_null_phase_from_lead_is_end_not_fit_before_the_update() -> None:
    routing = (d_choose(1, "alpha"),)
    lead = RecordingLead([led(None)])
    items = run(context(routing, pm=problem_map("a_one", 2), turn_no=3), RouterLlm(), lead)
    (decision,) = events(items)
    assert same_but_why(decision, d_end(3, "alpha", "not_fit"))
    assert isinstance(items[-1], FacilitatorUpdate) and items[-1].current_phase_id is None
    assert items.index(next(i for i in items if isinstance(i, RoutingEvent))) < len(items) - 1


def test_seam1_last_phase_with_exit_met_is_end_done_before_the_update() -> None:
    routing = (d_choose(1, "alpha"),)
    lead = RecordingLead([led("a_three", exit_met=True)])
    items = run(context(routing, pm=problem_map("a_three", 2), turn_no=3), RouterLlm(), lead)
    (decision,) = events(items)
    assert same_but_why(decision, d_end(3, "alpha", "done"))
    assert all(isinstance(i, ReplyDelta | RoutingEvent) for i in items[:-1])
    assert items[-1] == update("a_three", exit_met=True, reply="Що далі?")


def test_seam1_no_end_for_an_earlier_phase_with_exit_met_or_the_last_phase_without_it() -> None:
    for phase, met in (("a_two", True), ("a_one", True), ("a_three", False)):
        lead = RecordingLead([led(phase, exit_met=met)])
        items = run(context((d_choose(1, "alpha"),), pm=problem_map("a_one", 2)), RouterLlm(), lead)
        assert events(items) == [], (phase, met)
        assert items[-1] == update(phase, exit_met=met, reply="Що далі?")


def test_choose_then_null_from_lead_gives_choose_and_end_in_one_reply() -> None:
    llm = RouterLlm(generate=[choose("gamma")])
    lead = RecordingLead([led(None)])
    items = run(context((d_offer(1, "gamma", "beta"),), turn_no=3), llm, lead)
    got = events(items)
    assert len(got) == 2
    assert got[0] == d_choose(3, "gamma")
    assert same_but_why(got[1], d_end(3, "gamma", "not_fit"))
    assert isinstance(items[-1], FacilitatorUpdate)


def test_router_is_called_again_after_an_end_an_offer_an_ask_and_for_a_card_gone_from_the_revision() -> None:
    for routing in (
        (d_choose(1, "alpha"), d_end(3, "alpha", "done")),
        (d_offer(1, "alpha", "beta"),),
        (d_ask(1),),
        (d_choose(1, "zeta"),),
    ):
        llm, lead = RouterLlm(generate=[offer("beta", "gamma")]), RecordingLead()
        items = run(context(routing, card_id="zeta", turn_no=5), llm, lead)
        assert len(llm.router_calls) == 1, routing
        assert lead.contexts == []
        assert [d.kind for d in events(items)] == ["offer"]
