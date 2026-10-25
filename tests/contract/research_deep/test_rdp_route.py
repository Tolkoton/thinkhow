"""Contract tests of research-deep, the rules and the router side: `deep_question` of `RouterAnswer` (only
with `answer`, one retry, a blank one is `None`, trimmed on both paths), the new sentences of `router.md`
and `research.md`, the section of `deep_field.md` only under the router (slice tester; from the contract)."""

from typing import Any

import pytest
from pydantic import ValidationError
from rdp_fakes import (
    DEEP_FIELD_BODY,
    DEEP_FIELD_HEAD,
    DQ,
    QUESTION_HEAD,
    RESEARCH_SENTENCE,
    ROUTER_DEEP_SENTENCE,
    Stream,
    card_answer,
    fa,
    flat,
    full_deep,
    rq,
    with_deep_question,
)

from thinkhow.facilitation import FacilitationError, ResearchEvent, converse, respond
from thinkhow.facilitation.answer import answer_instruction
from thinkhow.facilitation.respond import RESEARCH_SECTION, system_instruction
from thinkhow.facilitation.route import ROUTER_RULES, RouterAnswer, route

OFFER = fa.router_raw("offer", ("alpha", "beta"), None, fa.OFFER_REPLY, "пропоную за профілем")


def test_router_deep_question_only_with_answer_otherwise_one_retry_then_an_error() -> None:
    assert RouterAnswer.model_validate_json(with_deep_question(fa.answer_raw(), DQ)).deep_question == DQ
    with pytest.raises(ValidationError):
        RouterAnswer.model_validate_json(with_deep_question(OFFER, DQ))
    ask = fa.router_raw("ask", (), None, "Що для вас важливо?")
    with pytest.raises(ValidationError):
        RouterAnswer.model_validate_json(with_deep_question(ask, DQ))
    choose = fa.router_raw("choose", (), "alpha", None)
    with pytest.raises(ValidationError):
        RouterAnswer.model_validate_json(with_deep_question(choose, DQ))

    llm = fa.FaLlm(generate=[with_deep_question(OFFER, DQ), OFFER])
    got = route(fa.context(()), fa.knowledge(), llm)
    assert got.action == "offer" and got.deep_question is None
    assert len(llm.router_calls) == 2
    twice = fa.FaLlm(generate=[with_deep_question(OFFER, DQ), with_deep_question(choose, DQ)])
    with pytest.raises(FacilitationError):
        route(fa.context(()), fa.knowledge(), twice)
    assert len(twice.router_calls) == 2


def test_deep_question_is_trimmed_and_a_blank_one_is_none_on_the_router_and_the_facilitator_path() -> None:
    padded = "  \n" + DQ + " \t"
    assert RouterAnswer.model_validate_json(with_deep_question(fa.answer_raw(), padded)).deep_question == DQ
    for blank in ("", "   ", "\n\t "):
        got = RouterAnswer.model_validate_json(with_deep_question(fa.answer_raw(), blank))
        assert got.deep_question is None, repr(blank)

    # the router path: the cycle gets the trimmed question
    llm = full_deep(router=[with_deep_question(fa.answer_raw(), padded)])
    items: list[Any] = list(converse(fa.context((), turn_no=1, history=[]), fa.knowledge(), llm, fa.no_lead))
    (plan,) = llm.of("plan")
    assert plan.contents[-1].text.endswith(QUESTION_HEAD + DQ)
    (ev,) = [i for i in items if isinstance(i, ResearchEvent)]
    assert ev.question == DQ

    # the facilitator under the router: the same
    raw = card_answer("Починаю дослідження.", "a_one", deep_question=padded)
    llm = full_deep(streams=[Stream(["Починаю дослідження."], raw, None)])
    items = list(respond(rq.context(), rq.knowledge(), llm))
    (plan,) = llm.of("plan")
    assert plan.contents[-1].text.endswith(QUESTION_HEAD + DQ)
    (ev,) = [i for i in items if isinstance(i, ResearchEvent)]
    assert ev.question == DQ


def test_router_md_answer_item_ends_with_the_sentence_about_agreeing_to_deep_research() -> None:
    rules = flat(ROUTER_RULES)
    assert flat(fa.ROUTER_ANSWER_ITEM) + " " + flat(ROUTER_DEEP_SENTENCE) in rules
    assert rules.count(flat(ROUTER_DEEP_SENTENCE)) == 1


def test_research_md_has_the_offer_sentence_between_the_s1_text_and_the_last_line() -> None:
    section = flat(RESEARCH_SECTION)
    assert flat(rq.RESEARCH_SECTION) + " " + flat(RESEARCH_SENTENCE) + " " + fa.RESEARCH_LAST_LINE in section
    assert RESEARCH_SECTION.split("\n")[-1] == fa.RESEARCH_LAST_LINE
    assert "deep_question" not in RESEARCH_SECTION


def test_deep_field_section_only_under_the_router_after_the_facts_and_before_the_card() -> None:
    routed = system_instruction(rq.ALPHA, [], None, routed=True)
    lines = routed.split("\n")
    assert lines.count(DEEP_FIELD_HEAD) == 1
    assert lines.index("# Факти про світ") < lines.index(DEEP_FIELD_HEAD) < lines.index("# Картка")
    assert flat(DEEP_FIELD_HEAD + "\n" + DEEP_FIELD_BODY) in flat(routed)
    for plain in (system_instruction(rq.ALPHA, [], None, routed=False), answer_instruction(None)):
        assert DEEP_FIELD_HEAD not in plain
        assert "deep_question" not in plain
    assert "deep_question" not in answer_instruction("Polski (pl-PL)")
