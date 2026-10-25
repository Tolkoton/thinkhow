"""Contract tests of fact-answer, the router side: `RouterAnswer` with `answer` (Seam 5), its one retry,
the new lines of `router.md` and the last line of `research.md` (slice tester; from the contract)."""

import pytest
from fa_fakes import (
    RESEARCH_LAST_LINE,
    ROUTER_ANSWER_ITEM,
    ROUTER_ASK_RULE,
    FaLlm,
    answer_raw,
    context,
    flat,
    knowledge,
    router_raw,
)
from pydantic import ValidationError

from thinkhow.facilitation import FacilitationError
from thinkhow.facilitation.respond import RESEARCH_SECTION
from thinkhow.facilitation.route import ROUTER_RULES, RouterAnswer, route

CANDIDATE_SETS: list[tuple[str, ...]] = [(), ("alpha",), ("alpha", "beta"), ("alpha", "beta", "pre-mortem")]


def test_seam5_answer_is_valid_only_without_a_card_id_with_0_to_3_candidates_and_any_reply() -> None:
    for cands in CANDIDATE_SETS:
        for reply in (None, "Ось що відомо про ціну."):
            got = RouterAnswer.model_validate_json(router_raw("answer", cands, None, reply))
            assert got.action == "answer" and got.card_id is None, (cands, reply)
            assert [c.card_id for c in got.candidates] == list(cands)
            with pytest.raises(ValidationError):
                RouterAnswer.model_validate_json(router_raw("answer", cands, "alpha", reply))


def test_seam5_an_answer_with_a_card_id_gets_the_one_retry_of_the_router_and_twice_is_an_error() -> None:
    llm = FaLlm(generate=[router_raw("answer", ("beta",), "beta", None), answer_raw(("alpha",))])
    got = route(context(()), knowledge(), llm)
    assert got.action == "answer" and got.card_id is None
    first, second = llm.router_calls
    assert len(llm.calls) == 2
    assert first.system == second.system and first.contents == second.contents
    twice = FaLlm(generate=[router_raw("answer", (), "beta", None), router_raw("answer", (), "alpha", "x")])
    with pytest.raises(FacilitationError):
        route(context(()), knowledge(), twice)
    assert len(twice.router_calls) == 2


def test_seam5_router_rules_have_the_answer_item_after_ask_and_before_why() -> None:
    rules = flat(ROUTER_RULES)
    item = flat(ROUTER_ANSWER_ITEM)
    assert item in rules
    ask = rules.index('- "ask" — ')
    why = rules.index("- why відповіді")
    assert ask < rules.index(item) < why


def test_seam5_router_rules_say_ask_does_not_ask_facts_of_the_world_among_the_rules() -> None:
    lines = ROUTER_RULES.split("\n")
    assert ROUTER_ASK_RULE in lines
    assert lines.index("Правила:") < lines.index(ROUTER_ASK_RULE)


def test_seam5_the_facts_section_ends_with_the_line_fact_only_for_what_search_found() -> None:
    lines = RESEARCH_SECTION.split("\n")
    assert lines[-1] == RESEARCH_LAST_LINE
    assert lines.count(RESEARCH_LAST_LINE) == 1
    assert lines[0] == "# Факти про світ"
