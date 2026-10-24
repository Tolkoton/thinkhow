"""Contract tests of the router: `RouterAnswer`, `router_schema`, `route` (Seam 4) and the router's system
instruction and frame (slice tester; from the contract, not the code)."""

import pytest
from pydantic import ValidationError
from rt_cards import ALPHA, BETA, GAMMA, HISTORY, problem_map
from rt_fakes import (
    PROFILE,
    PROFILE_OBJ,
    RULE_NONE,
    RULE_PL,
    RouterLlm,
    ask,
    choose,
    context,
    d_choose,
    d_end,
    d_offer,
    knowledge,
    offer,
    router_raw,
    why_of,
)

from thinkhow.facilitation import FacilitationError
from thinkhow.facilitation.route import ROUTER_RULES, RouterAnswer, route, router_schema
from thinkhow.facilitation.types import Candidate
from thinkhow.platform.llm import KnowledgeRev, Turn


def answer(
    action: str, candidates: list[tuple[str, str]], card_id: str | None, reply: str | None
) -> RouterAnswer:
    return RouterAnswer.model_validate(
        {
            "action": action,
            "profile": PROFILE,
            "candidates": [{"card_id": c, "why": w} for c, w in candidates],
            "card_id": card_id,
            "reply": reply,
            "why": "чому",
        }
    )


def test_router_answer_accepts_an_offer_of_two_or_three_different_candidates() -> None:
    two = answer("offer", [("alpha", "w1"), ("beta", "w2")], None, "Котрий ближчий?")
    three = answer("offer", [("alpha", "w1"), ("beta", "w2"), ("gamma", "w3")], None, "Котрий ближчий?")
    assert [c.card_id for c in two.candidates] == ["alpha", "beta"]
    assert [c.card_id for c in three.candidates] == ["alpha", "beta", "gamma"]


def test_router_answer_refuses_an_offer_of_one_four_or_repeated_candidates() -> None:
    for candidates in (
        [("alpha", "w1")],
        [],
        [("alpha", "w1"), ("beta", "w2"), ("gamma", "w3"), ("delta", "w4")],
        [("alpha", "w1"), ("alpha", "w1")],
    ):
        with pytest.raises(ValidationError):
            answer("offer", candidates, None, "Котрий ближчий?")


def test_router_answer_refuses_an_offer_without_a_reply() -> None:
    for reply in (None, ""):
        with pytest.raises(ValidationError):
            answer("offer", [("alpha", "w1"), ("beta", "w2")], None, reply)


def test_router_answer_ask_needs_a_non_empty_reply() -> None:
    ok = answer("ask", [], None, "Що для вас важливіше?")
    assert ok.reply == "Що для вас важливіше?"
    for reply in (None, ""):
        with pytest.raises(ValidationError):
            answer("ask", [], None, reply)


def test_router_answer_choose_needs_a_card_id() -> None:
    ok = answer("choose", [], "beta", None)
    assert ok.card_id == "beta"
    with pytest.raises(ValidationError):
        answer("choose", [], None, None)


def test_router_answer_refuses_more_than_three_candidates_for_ask_and_choose() -> None:
    four = [("alpha", "w1"), ("beta", "w2"), ("gamma", "w3"), ("delta", "w4")]
    with pytest.raises(ValidationError):
        answer("ask", four, None, "Що для вас важливіше?")
    with pytest.raises(ValidationError):
        answer("choose", four, "beta", None)


def test_router_schema_narrows_every_card_id_to_the_revision() -> None:
    schema = router_schema(knowledge())
    assert issubclass(schema, RouterAnswer)
    schema.model_validate_json(offer("alpha", "gamma"))
    schema.model_validate_json(choose("beta"))
    for raw in (offer("alpha", "zeta"), choose("zeta")):
        with pytest.raises(ValidationError):
            schema.model_validate_json(raw)


def test_route_makes_one_generate_json_call_with_the_router_schema_and_the_revision() -> None:
    llm = RouterLlm(generate=[offer("beta", "gamma")])
    k = knowledge()
    got = route(context(()), k, llm)
    assert len(llm.calls) == 1
    call = llm.calls[0]
    assert call.kind == "generate" and call.is_router
    assert call.rev == KnowledgeRev(rev=3, n=7)
    assert type(got) is RouterAnswer
    assert got.action == "offer" and got.profile == PROFILE_OBJ
    assert got.candidates == [
        Candidate(card_id="beta", why=why_of("beta")),
        Candidate(card_id="gamma", why=why_of("gamma")),
    ]


def test_route_retries_an_invalid_answer_once_with_the_same_call() -> None:
    for invalid in (offer("beta"), router_raw("choose", [], None, None), offer("beta", "zeta")):
        llm = RouterLlm(generate=[invalid, choose("gamma")])
        got = route(context((), language="Polski (pl-PL)"), knowledge(), llm)
        assert got.action == "choose" and got.card_id == "gamma"
        first, second = llm.calls
        assert first.is_router and second.is_router
        assert first.system == second.system
        assert first.contents == second.contents


def test_route_raises_facilitation_error_after_two_invalid_answers() -> None:
    llm = RouterLlm(generate=[offer("beta"), offer("beta", "zeta")])
    with pytest.raises(FacilitationError):
        route(context(()), knowledge(), llm)
    assert len(llm.router_calls) == 2


def test_router_system_instruction_is_rules_language_then_the_router_half_of_every_card() -> None:
    for language, rule in (("Polski (pl-PL)", RULE_PL), (None, RULE_NONE)):
        llm = RouterLlm(generate=[ask()])
        route(context((), language=language), knowledge(), llm)
        system = llm.calls[0].system
        head = f"{ROUTER_RULES}\n\n# Мова відповіді\n{rule}\n\n# Картка за карткою — для вибору\n"
        assert system.startswith(head)
        assert system.endswith("\n")
        cards = system[len(head) :]
        for c in (ALPHA, BETA, GAMMA):
            assert f"### {c.id} — {c.title}" in cards
            for text in (c.router.needs, *c.router.when_yes, *c.router.when_no, *c.router.signals):
                assert text in cards, text


def test_router_system_instruction_keeps_one_language_section_before_the_first_card_heading() -> None:
    llm = RouterLlm(generate=[ask()])
    route(context((), language="Polski (pl-PL)"), knowledge(), llm)
    lines = llm.calls[0].system.split("\n")
    assert lines.count("# Мова відповіді") == 1
    lang = lines.index("# Мова відповіді")
    first_card = next(i for i, line in enumerate(lines) if line.startswith("# Картка"))
    assert lang < first_card
    assert RULE_PL in "\n".join(lines[lang:first_card])


def test_router_system_instruction_has_no_facilitator_half_of_a_card() -> None:
    llm = RouterLlm(generate=[ask()])
    route(context(()), knowledge(), llm)
    system = llm.calls[0].system
    for c in (ALPHA, BETA, GAMMA):
        f = c.facilitator
        for text in (f.purpose, f.stance, f.needs, f.ending, f.pairs_well, *(t.text for t in f.traps)):
            assert text not in system, text
        for p in f.phases:
            for text in (p.goal, p.exit, *p.how):
                assert text not in system, text


def test_router_frame_is_history_then_one_frame_with_state_map_and_the_turn() -> None:
    routing = (d_offer(1, "alpha", "beta"), d_choose(3, "beta"), d_end(3, "beta", "not_fit"))
    ctx = context(routing, turn_no=5, text="Давай інакше.", pm=problem_map(None, 4))
    llm = RouterLlm(generate=[offer("alpha", "gamma")])
    route(ctx, knowledge(), llm)
    contents = llm.calls[0].contents
    assert contents[:-1] == [Turn(t.role, t.text) for t in HISTORY]
    assert contents[-1].role == "user"
    frame = contents[-1].text
    state = frame.index("[Стан вибору способу]")
    pmap = frame.index("[Карта проблеми зараз]")
    turn = frame.index("[Репліка людини #5]")
    assert state < pmap < turn
    assert frame.endswith("Давай інакше.")
    block = frame[state:pmap]
    lines = block.split("\n")
    assert any("alpha" in line and "beta" in line for line in lines)
    assert any("beta" in line and "not_fit" in line for line in lines)
