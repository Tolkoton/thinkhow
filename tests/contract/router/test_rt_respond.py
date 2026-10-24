"""Contract tests of `respond` branching and leading by the card under the router (Seam 3)
(slice tester; from the contract, not the code)."""

from rt_cards import HISTORY, problem_map
from rt_fakes import (
    FREE_MODE_LINE,
    ROUTED_HEAD,
    RULE_PL,
    RouterLlm,
    collect,
    context,
    d_choose,
    d_offer,
    events,
    fac_answer,
    knowledge,
    offer,
)
from rt_golden import FREE_CONTENTS, FREE_SYSTEM, PHASE_CONTENTS, PHASE_SYSTEM, TEXT

from thinkhow.facilitation import FacilitatorUpdate, ReplyDelta, respond
from thinkhow.platform.llm import Turn


def test_seam3_without_routing_system_and_frame_equal_the_golden_sample_of_5d90360() -> None:
    for pm, language, system, contents in (
        (problem_map(None, 2), "Polski (pl-PL)", FREE_SYSTEM, FREE_CONTENTS),
        (problem_map("a_one", 2), None, PHASE_SYSTEM, PHASE_CONTENTS),
    ):
        llm = RouterLlm(streams=[fac_answer("Що далі?", "a_two")])
        ctx = context(None, card_id="alpha", pm=pm, turn_no=3, text=TEXT, language=language)
        items = list(respond(ctx, knowledge(), llm))
        (call,) = llm.calls
        assert call.kind == "stream"
        assert call.system == system
        assert call.contents == [Turn(role, text) for role, text in contents]
        assert items == [
            ReplyDelta(text="Що далі?"),
            FacilitatorUpdate(
                reply="Що далі?", current_phase_id="a_two", phase_exit_met=False, map_updates=[]
            ),
        ]


def test_seam3_without_routing_no_routed_section() -> None:
    llm = RouterLlm(streams=[fac_answer("Що далі?", "a_two")])
    collect(lambda: respond(context(None, pm=problem_map(None, 2)), knowledge(), llm))
    assert ROUTED_HEAD not in llm.stream_calls[0].system


def test_seam3_under_the_router_routed_section_between_language_and_card_and_no_free_mode_line() -> None:
    routing = (d_offer(1, "alpha", "beta"), d_choose(1, "alpha"))
    llm = RouterLlm(streams=[fac_answer("Що далі?", "a_two")])
    ctx = context(routing, card_id="alpha", pm=problem_map(None, 2), language="Polski (pl-PL)")
    items, err = collect(lambda: respond(ctx, knowledge(), llm))
    assert err is None, err
    assert llm.router_calls == []
    (call,) = llm.stream_calls
    lines = call.system.split("\n")
    assert lines.count("# Мова відповіді") == 1
    lang = lines.index("# Мова відповіді")
    routed = lines.index(ROUTED_HEAD)
    card = lines.index("# Картка")
    assert lang < routed < card
    assert RULE_PL in "\n".join(lines[lang:routed])
    assert not any(line.startswith("# Картка") for line in lines[lang:card])
    assert FREE_MODE_LINE not in call.frame
    assert isinstance(items[-1], FacilitatorUpdate)


def test_respond_with_an_empty_routing_goes_to_the_router() -> None:
    llm = RouterLlm(generate=[offer("beta", "gamma")])
    items, err = collect(lambda: respond(context((), history=list(HISTORY)), knowledge(), llm))
    assert err is None, err
    assert len(llm.router_calls) == 1
    assert llm.stream_calls == []
    assert [d.kind for d in events(items)] == ["offer"]
