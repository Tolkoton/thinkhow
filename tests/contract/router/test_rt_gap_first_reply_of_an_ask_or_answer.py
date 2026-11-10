"""Bug 004: a topic opened by the router's ask or by a fact answer never tells that the opinion can be asked.

Task 310, variant A: the first reply of a topic says the system's opinion can be asked any time. The
facilitator gets FIRST_REPLY_LINE only while the topic's history has no model turn (one-conversation Q4,
Seam 5), so after an ask or a fact answer on turn 1 the card led on turn 3 gets no line. The line must then
be in the frame of the reply that is the topic's first — the router's ask or the fact answer — and say itself
what to tell: `router.md` and `answer.md` are fixed byte for byte by sealed tests (spoken_replies I1,
router_unknown_fact), and neither has a rule for the line.
"""

from __future__ import annotations

import json
from typing import Any, cast

from rt_fakes import RouterLlm, ask, choose, context, d_ask, events, fac_answer, knowledge, router_raw

from thinkhow.facilitation.respond import FIRST_REPLY_LINE, respond
from thinkhow.facilitation.types import Decision, Turn

FIRST_REPLY = "[Стан] Перша відповідь у темі"
OPINION = "«що б ти обрав?»"
FACT = json.dumps(
    {"reply": "Зазвичай це 3–5 тисяч. Що з цього важливо далі?", "map_updates": []}, ensure_ascii=False
)


def test_the_line_itself_tells_what_to_say_before_the_question() -> None:
    """The ask and the fact answer have no rule for the line, so the line carries it."""
    assert FIRST_REPLY_LINE.startswith(FIRST_REPLY)
    assert (
        OPINION in FIRST_REPLY_LINE
        and "перед питанням" in FIRST_REPLY_LINE
        and "інший спосіб" in FIRST_REPLY_LINE
    )


def _first_reply(llm: RouterLlm) -> Decision:
    items = list(respond(context((), turn_no=1, history=[]), knowledge(), cast(Any, llm)))
    (decision,) = events(items)
    return decision


def _turn_three(first: Decision, reply: str) -> RouterLlm:
    """Turn 3 of the same topic: the router chooses alpha, and the card is led."""
    history = [Turn("user", "Хочу подумати."), Turn("model", reply)]
    llm = RouterLlm(generate=[choose("alpha")], streams=[fac_answer("Схоже, що … Що головне?", "a_one")])
    items = list(respond(context((first,), turn_no=3, history=history), knowledge(), cast(Any, llm)))
    assert [d.kind for d in events(items)] == ["choose"]
    return llm


def test_a_topic_opened_by_the_routers_ask_tells_the_opinion_can_be_asked_in_that_ask() -> None:
    llm = RouterLlm(generate=[ask()])
    first = _first_reply(llm)
    assert first.kind == "ask" and llm.stream_calls == []
    assert FIRST_REPLY_LINE in llm.router_calls[0].frame, (
        "the ask is the topic's first reply, its frame has no line"
    )
    later = _turn_three(first, "Це радше про гроші чи про час?")
    assert all(FIRST_REPLY_LINE not in c.frame for c in later.calls)


def test_a_topic_opened_by_a_fact_answer_tells_the_opinion_can_be_asked_in_that_answer() -> None:
    llm = RouterLlm(generate=[router_raw("answer")], streams=[FACT])
    first = _first_reply(llm)
    assert first.kind == "answer"
    (stream,) = llm.stream_calls
    assert FIRST_REPLY_LINE in stream.frame, (
        "the fact answer is the topic's first reply, its frame has no line"
    )
    later = _turn_three(first, "Зазвичай це 3–5 тисяч.")
    assert all(FIRST_REPLY_LINE not in c.frame for c in later.calls)


def test_a_later_ask_carries_no_first_reply_line() -> None:
    history = [Turn("user", "Привіт"), Turn("model", "Вітаю")]
    llm = RouterLlm(generate=[ask()])
    list(respond(context((d_ask(1),), turn_no=3, history=history), knowledge(), cast(Any, llm)))
    assert FIRST_REPLY_LINE not in llm.router_calls[0].frame
