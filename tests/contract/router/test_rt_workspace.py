"""Contract tests of workspace under the router: routing.json read, passed and appended (Seam «workspace»),
the three-turn conversation through `workspace.reply` (Seam 2) and an invalid router through it (Seam 4)
(slice tester; from the contract, not the code)."""

from functools import partial
from pathlib import Path
from typing import Any

import pytest
from rt_cards import BETA, GAMMA
from rt_fakes import (
    ALICE,
    OFFER_REPLY,
    T0,
    Down,
    RouterLlm,
    ScenarioFacilitate,
    choose,
    d_ask,
    d_choose,
    d_end,
    d_offer,
    fac_answer,
    knowledge,
    offer,
    put_raw_routing,
    put_routing,
    raw_routing,
    read_routing,
    router_raw,
    same_but_why,
    topic,
    update,
)

from thinkhow.facilitation import respond
from thinkhow.facilitation.types import ReplyDelta, RoutingEvent
from thinkhow.platform.storage import LocalStorage
from thinkhow.workspace import Answered, Delta, Failed, open_topic, reply, retry


def answered(store: LocalStorage, fac: Any, ref: Any, text: str) -> list[Any]:
    return list(reply(store, fac, ALICE, ref, text, T0))


def test_without_routing_json_the_context_has_an_empty_routing_and_the_default_card(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    ref = topic(store)
    fac = ScenarioFacilitate([[ReplyDelta("Привіт?"), update(None, reply="Привіт?")]])
    assert isinstance(answered(store, fac, ref, "Хочу подумати.")[-1], Answered)
    (ctx,) = fac.contexts
    assert ctx.routing == ()
    assert ctx.card_id == "pre-mortem"


def test_routing_json_is_passed_as_a_tuple_and_the_card_of_a_last_choose_is_the_card(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    ref = topic(store)
    before = [d_offer(1, "beta", "gamma"), d_choose(3, "beta")]
    put_routing(store, ref, before)
    fac = ScenarioFacilitate([[ReplyDelta("Далі?"), update("b_one", reply="Далі?")]])
    answered(store, fac, ref, "Так.")
    (ctx,) = fac.contexts
    assert ctx.routing == tuple(before)
    assert ctx.card_id == "beta"


def test_with_a_last_decision_not_choose_the_card_is_the_default(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    ref = topic(store)
    before = [d_choose(1, "beta"), d_end(1, "beta", "not_fit"), d_ask(3)]
    put_routing(store, ref, before)
    fac = ScenarioFacilitate([[ReplyDelta("Далі?"), update(None, reply="Далі?")]])
    answered(store, fac, ref, "Так.")
    (ctx,) = fac.contexts
    assert ctx.routing == tuple(before)
    assert ctx.card_id == "pre-mortem"


def test_routing_events_are_not_deltas_and_are_appended_after_a_successful_answer(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    ref = topic(store)
    put_routing(store, ref, [d_offer(1, "beta", "gamma")])
    new = [d_choose(3, "gamma"), d_end(3, "gamma", "not_fit")]
    script: list[Any] = [
        RoutingEvent(new[0]),
        ReplyDelta("Добре."),
        RoutingEvent(new[1]),
        update(None, reply="Добре."),
    ]
    fac = ScenarioFacilitate([script])
    got = answered(store, fac, ref, "Друге.")
    assert [e for e in got if isinstance(e, Delta)] == [Delta("Добре.")]
    assert isinstance(got[-1], Answered)
    assert read_routing(store, ref) == [d_offer(1, "beta", "gamma"), *new]


def test_routing_json_is_not_written_when_the_stream_brings_no_routing_event(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    ref = topic(store)
    fac = ScenarioFacilitate(
        [
            [ReplyDelta("Привіт?"), update(None, reply="Привіт?")],
            [RoutingEvent(d_choose(3, "beta")), ReplyDelta("Далі?"), update("b_one", reply="Далі?")],
            [ReplyDelta("А ще?"), update("b_two", reply="А ще?")],
        ]
    )
    assert isinstance(answered(store, fac, ref, "Хочу подумати.")[-1], Answered)
    assert raw_routing(store, ref) is None
    assert isinstance(answered(store, fac, ref, "Перше.")[-1], Answered)
    before = raw_routing(store, ref)
    assert read_routing(store, ref) == [d_choose(3, "beta")]
    assert isinstance(answered(store, fac, ref, "Так.")[-1], Answered)
    assert raw_routing(store, ref) == before


def test_routing_json_is_not_written_on_failed(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    ref = topic(store)
    fac = ScenarioFacilitate(
        [
            [RoutingEvent(d_offer(1, "beta", "gamma")), ReplyDelta("Котрий?"), update(None, reply="Котрий?")],
            [RoutingEvent(d_choose(3, "beta")), ReplyDelta("Да"), Down("down")],
            [RoutingEvent(d_choose(3, "gamma")), ReplyDelta("Далі?"), update("g_only", reply="Далі?")],
        ]
    )
    assert isinstance(answered(store, fac, ref, "Хочу подумати.")[-1], Answered)
    before = raw_routing(store, ref)
    assert read_routing(store, ref) == [d_offer(1, "beta", "gamma")]
    assert isinstance(answered(store, fac, ref, "Перше.")[-1], Failed)
    assert raw_routing(store, ref) == before
    assert isinstance(list(retry(store, fac, ALICE, ref, T0))[-1], Answered)
    assert read_routing(store, ref) == [d_offer(1, "beta", "gamma"), d_choose(3, "gamma")]


def test_a_corrupt_routing_json_is_a_parse_error_without_recovery(tmp_path: Path) -> None:
    for data in (b"not json", b'{"items": []}', b'{"decisions": [{"turn": 1}]}'):
        store = LocalStorage(tmp_path / str(len(data)))
        ref = topic(store)
        put_raw_routing(store, ref, data)
        fac = ScenarioFacilitate([[ReplyDelta("Далі?"), update(None, reply="Далі?")]])
        with pytest.raises(Exception) as caught:
            answered(store, fac, ref, "Так.")
        assert not isinstance(caught.value, NotImplementedError)
        assert fac.contexts == []
        assert raw_routing(store, ref) == data


def test_seam2_offer_choose_end_and_back_to_the_router_through_workspace_reply(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    ref = topic(store)
    k = knowledge()
    llm = RouterLlm(
        generate=[offer("beta", "gamma"), choose("beta"), offer("gamma", "alpha")],
        streams=[
            fac_answer("Що ви вже знаєте?", "b_one"),
            fac_answer("Що для вас зараз найважливіше?", None),
        ],
    )
    fac = partial(respond, knowledge=k, llm=llm)

    # 1: a new topic → the router offers, its text is the answer
    got = answered(store, fac, ref, "Не знаю, чи відкривати кав'ярню.")
    assert isinstance(got[-1], Answered)
    assert "".join(e.text for e in got if isinstance(e, Delta)) == OFFER_REPLY
    assert read_routing(store, ref) == [d_offer(1, "beta", "gamma")]
    assert len(llm.router_calls) == 1 and llm.stream_calls == []
    assert open_topic(store, ALICE, ref, T0).sessions[-1].turns[-1].text == OFFER_REPLY

    # 2: «перше» → choose + the facilitator's answer on the chosen card, in the same reply
    got = answered(store, fac, ref, "Перше.")
    assert isinstance(got[-1], Answered)
    assert read_routing(store, ref) == [d_offer(1, "beta", "gamma"), d_choose(3, "beta")]
    assert len(llm.router_calls) == 2 and len(llm.stream_calls) == 1
    led = llm.stream_calls[0]
    assert BETA.facilitator.purpose in led.system and "Заголовок beta" in led.system
    assert "Заголовок pre-mortem" not in led.system and GAMMA.facilitator.purpose not in led.system
    assert open_topic(store, ALICE, ref, T0).problem_map.phase_id == "b_one"

    # 3: the facilitator returns null → end: not_fit, no router call
    got = answered(store, fac, ref, "Мені це не підходить.")
    assert isinstance(got[-1], Answered)
    decisions = read_routing(store, ref)
    assert decisions is not None and len(decisions) == 3
    assert decisions[:2] == [d_offer(1, "beta", "gamma"), d_choose(3, "beta")]
    assert same_but_why(decisions[2], d_end(5, "beta", "not_fit"))
    assert len(llm.router_calls) == 2 and len(llm.stream_calls) == 2
    assert BETA.facilitator.purpose in llm.stream_calls[1].system

    # 4: back to the router; its frame names the ended card and not_fit; its system has no phase texts
    got = answered(store, fac, ref, "Що тепер?")
    assert isinstance(got[-1], Answered)
    decisions = read_routing(store, ref)
    assert decisions is not None and len(decisions) == 4
    assert decisions[3] == d_offer(7, "gamma", "alpha")
    assert len(llm.router_calls) == 3 and len(llm.stream_calls) == 2
    last = llm.router_calls[-1]
    state = last.frame[last.frame.index("[Стан вибору способу]") : last.frame.index("[Карта проблеми зараз]")]
    assert any("beta" in line and "not_fit" in line for line in state.split("\n"))
    for c in k.cards.values():
        for p in c.facilitator.phases:
            assert p.goal not in last.system and p.exit not in last.system


def test_seam4_router_invalid_twice_through_workspace_is_failed_and_file_unchanged(
    tmp_path: Path,
) -> None:
    store = LocalStorage(tmp_path)
    ref = topic(store)
    llm = RouterLlm(generate=[offer("beta"), offer("beta", "zeta")])
    got = answered(store, partial(respond, knowledge=knowledge(), llm=llm), ref, "Хочу подумати.")
    assert isinstance(got[-1], Failed)
    assert len(llm.router_calls) == 2
    assert raw_routing(store, ref) is None
    put_routing(store, ref, [d_choose(1, "beta"), d_end(1, "beta", "done")])
    before = raw_routing(store, ref)
    no_card = router_raw("choose", [], None, None)
    llm = RouterLlm(generate=[no_card, no_card])
    got = list(retry(store, partial(respond, knowledge=knowledge(), llm=llm), ALICE, ref, T0))
    assert isinstance(got[-1], Failed)
    assert raw_routing(store, ref) == before
