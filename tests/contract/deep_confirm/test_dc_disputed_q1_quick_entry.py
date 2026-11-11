"""Disputed test of deep-research-confirm-first (question Q1; sealed after the planner's answer).

Q1: I2 says the answer that decides to research deep «не пише в research.json», while «Швидкий пошук у
відповіді (S1 research-quick) — без змін». Under the card one answer can carry both: the facilitator's own
quick search (its stream found sources) and a deep_question. The reading taken: I2 is about the deep cycle —
that answer adds no deep entry and makes no search call; the quick search's entry of the same answer is
written as before.
"""

from pathlib import Path

from dc_fakes import (
    CARD_REPLY,
    DQ,
    FILE_1,
    PLAN_RAW_1,
    PROPOSAL_1,
    DcLlm,
    Stream,
    card_raw,
    fa,
    fac,
    new_topic,
    pending_file,
    rq,
    say,
    store_at,
)

from thinkhow.workspace import Answered


def test_q1_a_proposal_under_the_card_keeps_the_quick_search_entry_of_the_same_answer(tmp_path: Path) -> None:
    ref = new_topic(tmp_path, "alpha")
    stream = Stream([CARD_REPLY], card_raw(CARD_REPLY, "a_one", DQ), fa.FOUND)
    llm = DcLlm(streams=[stream], plans=[PLAN_RAW_1])
    got, shown = say(tmp_path, fac(llm), ref, "Скільки коштує консалтинг? І досліди ринок глибоко.")
    assert got[-1] == Answered(2), got[-1]
    assert shown.startswith(CARD_REPLY) and shown.endswith(PROPOSAL_1)
    assert llm.prompts() == [] and llm.of("report") == []
    entries = rq.read_research(store_at(tmp_path), ref)
    assert entries is not None
    assert [(e["turn"], e["depth"]) for e in entries] == [(2, "quick")]
    assert pending_file(tmp_path, ref) == {"turn": 2, "pending": FILE_1}
