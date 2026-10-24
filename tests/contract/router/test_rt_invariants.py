"""One test per invariant I1–I5 of the router contract, inputs chosen by hand from each «Domain»
(slice tester; from the contract, not the code)."""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

from rt_cards import ALPHA, BETA, GAMMA, HISTORY, MEMORY, problem_map
from rt_fakes import (
    ALICE,
    FREE_MODE_LINE,
    ROUTED_HEAD,
    T0,
    Down,
    RecordingLead,
    RouterLlm,
    ScenarioFacilitate,
    ask,
    choose,
    context,
    d_ask,
    d_choose,
    d_end,
    d_offer,
    events,
    fac_answer,
    knowledge,
    led,
    offer,
    put_routing,
    raw_routing,
    read_routing,
    router_raw,
    run_converse,
    topic,
    update,
)

from thinkhow.facilitation import (
    FacilitationError,
    FacilitatorUpdate,
    ReplyDelta,
    RoutingEvent,
    respond,
)
from thinkhow.facilitation.types import FacilitationContext, Rev
from thinkhow.knowledge import CurrentKnowledge
from thinkhow.platform.storage import LocalStorage
from thinkhow.workspace import Answered, Failed, reply, retry


def test_I1_every_routing_event_comes_before_the_one_last_update() -> None:
    chosen = (d_choose(1, "alpha"),)
    cases = [
        ((), [offer("beta", "gamma")], []),
        ((), [ask()], []),
        ((), [choose("beta")], [led("b_one")]),
        ((), [choose("beta")], [led(None)]),
        ((), [choose("gamma")], [led("g_only", exit_met=True)]),
        ((d_offer(1, "alpha", "beta"),), [choose("alpha")], [led("a_three", exit_met=True)]),
        ((d_ask(1),), [ask()], []),
        (chosen, [], [led("a_two")]),
        (chosen, [], [led(None)]),
        (chosen, [], [led("a_three", exit_met=True)]),
        ((d_choose(1, "alpha"), d_end(3, "alpha", "done")), [offer("beta", "gamma")], []),
        ((d_choose(1, "alpha"), d_end(3, "alpha", "not_fit")), [choose("beta")], [led(None)]),
        ((d_choose(1, "zeta"),), [choose("gamma")], [led("g_only", exit_met=True)]),
    ]
    for routing, generate, scripts in cases:
        llm, lead = RouterLlm(generate=list(generate)), RecordingLead(list(scripts))
        items, err = run_converse(context(routing, turn_no=5), knowledge(), llm, lead)
        assert err is None, (routing, err)
        ups = [i for i, item in enumerate(items) if isinstance(item, FacilitatorUpdate)]
        assert ups == [len(items) - 1], (routing, generate, items)
        assert all(isinstance(item, ReplyDelta | RoutingEvent) for item in items[:-1]), items


def test_I2_routing_json_is_the_earlier_decisions_unchanged_plus_the_new_ones_and_failed_changes_nothing(
    tmp_path: Path,
) -> None:
    # a file of three decisions: success with two new, Failed, NoUpdate, success with none, one new
    store = LocalStorage(tmp_path / "long")
    ref = topic(store)
    earlier = [d_offer(1, "alpha", "beta"), d_choose(3, "alpha"), d_end(5, "alpha", "done")]
    put_routing(store, ref, earlier)
    new_two = [d_choose(7, "beta"), d_end(7, "beta", "not_fit")]
    new_one = [d_ask(11)]
    fac = ScenarioFacilitate(
        [
            [
                RoutingEvent(new_two[0]),
                ReplyDelta("Так?"),
                RoutingEvent(new_two[1]),
                update(None, reply="Так?"),
            ],
            [RoutingEvent(d_offer(9, "gamma", "beta")), ReplyDelta("Ну"), Down("down")],
            [RoutingEvent(d_offer(9, "gamma", "beta")), ReplyDelta("Ну")],
            [ReplyDelta("Добре?"), update(None, reply="Добре?")],
            [RoutingEvent(new_one[0]), ReplyDelta("Що саме?"), update(None, reply="Що саме?")],
        ]
    )
    assert isinstance(list(reply(store, fac, ALICE, ref, "Друге.", T0))[-1], Answered)
    assert read_routing(store, ref) == [*earlier, *new_two]
    before = raw_routing(store, ref)
    assert isinstance(list(reply(store, fac, ALICE, ref, "Інше.", T0))[-1], Failed)
    assert raw_routing(store, ref) == before
    assert isinstance(list(retry(store, fac, ALICE, ref, T0))[-1], Failed)
    assert raw_routing(store, ref) == before
    assert isinstance(list(retry(store, fac, ALICE, ref, T0))[-1], Answered)
    assert read_routing(store, ref) == [*earlier, *new_two]
    assert isinstance(list(reply(store, fac, ALICE, ref, "Ще.", T0))[-1], Answered)
    assert read_routing(store, ref) == [*earlier, *new_two, *new_one]

    # no file: choose → the facilitator invalid twice → Failed, no file; then the router again
    store = LocalStorage(tmp_path / "new")
    ref = topic(store)
    bad_update = '{"current_phase_id": "zzz", "phase_exit_met": false, "map_updates": []}'
    llm = RouterLlm(
        generate=[choose("beta"), bad_update, offer("gamma", "alpha")],
        streams=[fac_answer("Що ви знаєте?", "zzz")],
    )
    k = knowledge()

    def fac2(ctx: FacilitationContext) -> Iterator[Any]:
        return respond(ctx, k, llm)

    assert isinstance(list(reply(store, fac2, ALICE, ref, "Хочу перше.", T0))[-1], Failed)
    assert raw_routing(store, ref) is None
    assert isinstance(list(retry(store, fac2, ALICE, ref, T0))[-1], Answered)
    assert read_routing(store, ref) == [d_offer(1, "gamma", "alpha")]


def test_I3_the_facilitator_gets_a_card_only_after_a_last_choose_and_only_that_card() -> None:
    gone = (d_choose(1, "zeta"),)
    cases = [
        ((), [offer("alpha", "beta")], None),
        ((), [ask()], None),
        ((d_offer(1, "alpha", "beta"),), [ask()], None),
        ((d_offer(1, "alpha", "beta"),), [choose("beta")], "beta"),
        ((d_choose(1, "alpha"),), [], "alpha"),
        ((d_choose(1, "alpha"), d_end(3, "alpha", "not_fit")), [offer("beta", "gamma")], None),
        (
            (d_choose(1, "alpha"), d_end(3, "alpha", "done"), d_offer(5, "beta", "gamma")),
            [choose("alpha")],
            "alpha",
        ),
        (gone, [offer("alpha", "beta")], None),
        (gone, [ask()], None),
        (gone, [choose("gamma")], "gamma"),
    ]
    for routing, generate, card in cases:
        llm = RouterLlm(generate=list(generate))
        lead = RecordingLead([led("a_one" if card == "alpha" else "b_one" if card == "beta" else "g_only")])
        ctx = context(routing, card_id="zeta" if routing == gone else "alpha", turn_no=7)
        items, err = run_converse(ctx, knowledge(), llm, lead)
        assert err is None, (routing, err)
        if card is None:
            assert lead.contexts == [], routing
        else:
            assert [c.card_id for c in lead.contexts] == [card], routing
        assert llm.generate == [], routing


def test_I4_every_offer_and_choose_names_cards_of_the_revision_and_carries_its_pair() -> None:
    k1 = knowledge((ALPHA, BETA, GAMMA), rev=3, n=7)
    k2 = knowledge((ALPHA, GAMMA), rev=4, n=0)
    invalid = {
        "k1": [
            offer("alpha"),
            offer("alpha", "alpha"),
            offer("alpha", "beta", "gamma", "alpha"),
            offer("alpha", "zeta"),
            choose("zeta"),
            router_raw("choose", [], None, None),
            router_raw("offer", [("alpha", "w"), ("beta", "w")], None, None),
        ],
        "k2": [offer("alpha", "beta"), choose("beta"), offer("gamma")],
    }
    valid = {
        "k1": [offer("alpha", "beta", "gamma"), offer("gamma", "beta"), choose("beta")],
        "k2": [offer("gamma", "alpha"), choose("gamma")],
    }
    for name, k in (("k1", k1), ("k2", k2)):
        for raw in invalid[name]:
            llm = RouterLlm(generate=[raw, raw])
            items, err = run_converse(context(()), k, llm, RecordingLead())
            assert isinstance(err, FacilitationError), (name, raw, err)
            assert events(items) == []
        for raw in valid[name]:
            llm = RouterLlm(generate=[raw])
            lead = RecordingLead([led(None)])
            items, err = run_converse(context(()), k, llm, lead)
            assert err is None, (name, raw, err)
            first = events(items)[0]
            assert first.rev == Rev(rev=k.rev, n=k.n)
            if first.kind == "offer":
                ids = [c.card_id for c in first.candidates]
                assert 2 <= len(ids) <= 3 and len(set(ids)) == len(ids)
                assert set(ids) <= set(k.cards)
            else:
                assert first.kind == "choose" and first.card_id in k.cards


def test_I5_without_routing_respond_is_as_before_and_under_the_router_routing_is_never_none(
    tmp_path: Path,
) -> None:
    # routing None: no router, no RoutingEvent, no routed section, the free-mode line by the old rule
    for card, memory, language, pm, history in (
        (ALPHA, MEMORY, None, problem_map(None, 2), HISTORY),
        (BETA, [], "Polski (pl-PL)", problem_map(None, 0), []),
        (GAMMA, MEMORY, None, problem_map("g_only", 4), HISTORY),
        (ALPHA, [], "Polski (pl-PL)", problem_map("a_three", 0), []),
    ):
        k = CurrentKnowledge(rev=2, n=1, cards={c.id: c for c in (ALPHA, BETA, GAMMA)}, memory=list(memory))
        phase = card.facilitator.phases[0].id
        llm = RouterLlm(streams=[fac_answer("Що далі?", phase)])
        ctx = context(None, card_id=card.id, pm=pm, language=language, history=list(history))
        items = list(respond(ctx, k, llm))
        assert llm.router_calls == [] and events(items) == []
        (call,) = llm.stream_calls
        assert ROUTED_HEAD not in call.system
        assert (FREE_MODE_LINE in call.frame) == (pm.phase_id is None and pm.last_turn > 0)
        assert items[-1] == update(phase, reply="Що далі?")

    # converse never hands routing=None to the lead
    for routing, generate in (
        ((), [choose("beta")]),
        ((d_choose(1, "alpha"),), []),
        ((d_ask(1),), [choose("gamma")]),
    ):
        lead = RecordingLead([led("b_one")])
        run_converse(context(routing), knowledge(), RouterLlm(generate=list(generate)), lead)
        assert len(lead.contexts) == 1 and lead.contexts[0].routing is not None, routing

    # workspace never passes routing=None: without the file and with it
    store = LocalStorage(tmp_path)
    ref = topic(store)
    fac = ScenarioFacilitate(
        [[ReplyDelta("А?"), update(None, reply="А?")], [ReplyDelta("Б?"), update(None, reply="Б?")]]
    )
    list(reply(store, fac, ALICE, ref, "Перша.", T0))
    put_routing(store, ref, [d_ask(1)])
    list(reply(store, fac, ALICE, ref, "Друга.", T0))
    assert [c.routing for c in fac.contexts] == [(), (d_ask(1),)]
