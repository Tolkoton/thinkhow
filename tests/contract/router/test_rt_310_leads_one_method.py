"""Task 310: the router chooses one method itself and the facilitator leads by it at once; variant A.

The owner's words (2026-10-27): «Тут було добре, якби він сам … вів якимось методом, просто … називав яким.»
Variant A (Claude's proposal the owner took): the first reply says the system's opinion can be asked any time;
every reply gives something of its own before one question.
"""

from __future__ import annotations

from typing import Any, cast

from rt_fakes import (
    RecordingLead,
    RouterLlm,
    choose,
    context,
    d_choose,
    d_end,
    events,
    fac_answer,
    knowledge,
    led,
    run_converse,
)

from thinkhow.facilitation.respond import FIRST_REPLY_LINE, JUST_CHOSEN_LINE, RULES, _state, respond
from thinkhow.facilitation.route import ROUTER_RULES, _decision_line
from thinkhow.facilitation.types import Turn

FIRST_REPLY = "[Стан] Перша відповідь у темі"


# --- the router chooses, it does not offer a list ---


def test_the_router_rules_choose_one_card_itself_and_never_ask_for_an_offer() -> None:
    """No offer item; the one mention left is fact-answer's sealed sentence (contract line 52)."""
    assert '- "offer"' not in ROUTER_RULES and "2 або 3 картки" not in ROUTER_RULES
    assert ROUTER_RULES.count('"offer"') == 1 and 'не "answer", а "offer" чи "ask".' in ROUTER_RULES
    assert "обери сам одну картку" in ROUTER_RULES
    assert "Людина не обирає зі списку" in ROUTER_RULES


def test_the_router_rules_keep_another_way_on_request_and_a_named_method() -> None:
    assert "«давай інакше»" in ROUTER_RULES and "обери інший спосіб" in ROUTER_RULES
    assert "«хочу провести пре-мортем»" in ROUTER_RULES


def test_an_ask_of_the_router_gives_something_of_its_own_before_the_question() -> None:
    ask_rule = ROUTER_RULES[ROUTER_RULES.index('  - "ask"') : ROUTER_RULES.index('  - "answer"')]
    assert "спершу одне речення свого" in ask_rule


def test_the_routing_state_no_longer_says_the_person_chose() -> None:
    line = _decision_line(d_choose(1, "alpha"))
    assert line == "- репліка #1: choose alpha (обрано)"


def test_a_choose_on_the_first_turn_leads_the_card_on_that_same_turn() -> None:
    llm = RouterLlm(generate=[choose("beta", why="система обрала за профілем")])
    lead = RecordingLead(scripts=[led("b_one")])
    ctx = context((), turn_no=1, history=[])
    items, error = run_converse(ctx, knowledge(), llm, lead)
    assert error is None
    assert [d.kind for d in events(items)] == ["choose"] and events(items)[0].card_id == "beta"
    assert [c.card_id for c in lead.contexts] == ["beta"]


def test_after_another_way_the_router_chooses_again_without_a_list() -> None:
    """«Давай інакше» ended the card as not fitting; the next turn routes, and a choose leads the new card."""
    before = (d_choose(1, "alpha"), d_end(3, "alpha", "not_fit"))
    llm, lead = RouterLlm(generate=[choose("gamma")]), RecordingLead(scripts=[led("g_only")])
    items, error = run_converse(context(before, turn_no=5), knowledge(), llm, lead)
    assert error is None
    assert [d.kind for d in events(items)] == ["choose"]
    assert [c.card_id for c in lead.contexts] == ["gamma"]


# --- variant A: the facilitator ---


def test_every_reply_gives_its_own_before_one_question_and_the_person_decides() -> None:
    assert "Спершу своє, потім питання." in RULES
    assert "факт, спостереження чи гіпотезу з причиною" in RULES
    assert "Рішення ухвалює людина" in RULES


def test_the_first_reply_rule_tells_the_opinion_can_be_asked() -> None:
    assert f"«{FIRST_REPLY}»" in RULES and "«що б ти обрав?»" in RULES
    assert FIRST_REPLY_LINE.startswith(FIRST_REPLY)


def test_the_first_reply_of_a_topic_carries_the_line_after_the_chosen_method() -> None:
    state = _state(context((d_choose(1, "alpha"),), turn_no=1, history=[]))
    assert state.startswith(JUST_CHOSEN_LINE) and FIRST_REPLY_LINE in state


def test_a_later_reply_has_no_first_reply_line() -> None:
    history = [Turn("user", "Привіт"), Turn("model", "Вітаю")]
    assert FIRST_REPLY_LINE not in _state(context((d_choose(3, "alpha"),), turn_no=3, history=history))
    assert FIRST_REPLY_LINE not in _state(context((), turn_no=3, history=history))


def test_without_the_router_nothing_changes() -> None:
    assert FIRST_REPLY_LINE not in _state(context(None, turn_no=1, history=[]))


def test_respond_streams_the_card_with_both_lines_on_the_first_turn() -> None:
    llm = RouterLlm(
        generate=[choose("alpha")], streams=[fac_answer("Схоже, що … Що для вас головне?", "a_one")]
    )
    items = list(respond(context((), turn_no=1, history=[]), knowledge(), cast(Any, llm)))
    assert [d.kind for d in events(items)] == ["choose"]
    frame = llm.stream_calls[0].frame
    assert JUST_CHOSEN_LINE in frame and FIRST_REPLY_LINE in frame
