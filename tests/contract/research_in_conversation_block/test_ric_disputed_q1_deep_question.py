"""Block test of research-in-conversation held apart: it depends on question Q1 of the hand-in.

The «Inter-slice contracts» line for S3 puts `deep_question` on `FacilitatorUpdate`; the appendix amendment
from planning S3 puts it in the facilitator's schema under the router and in `RouterAnswer`. The test takes
the amendment. Slice tester, mode `block`; from the feature artifact and the public signatures.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from ric_fakes import fa, facilitate, rdp, rq, say

from thinkhow.facilitation import respond
from thinkhow.facilitation.route import router_schema
from thinkhow.platform.storage import LocalStorage
from thinkhow.workspace import Answered

PLAIN_REPLY = "Що для вас у цьому найважливіше?"
SOURCES_ABC = [
    {"title": "Mittelstand Studie", "url": "https://a.example/mittelstand"},
    {"title": "Beratermarkt", "url": "https://b.example/markt"},
    {"title": "IHK Leipzig", "url": "https://c.example/ihk"},
]


def deep_entry(turn: int) -> dict[str, Any]:
    return {
        "turn": turn,
        "depth": "deep",
        "queries": list(rdp.QUERIES_ABC),
        "sources": SOURCES_ABC,
        "suggestions_html": "<div>підказки Б</div>",
        "question": rdp.DQ,
        "report": rdp.REPORT,
    }


def card_raw(reply: str, updates: Sequence[dict[str, Any]] = (), deep_question: Any = None) -> str:
    if deep_question is None:
        raw: str = rdp.card_answer(reply, "a_one", False, list(updates))
    else:
        raw = rdp.card_answer(reply, "a_one", False, list(updates), deep_question=deep_question)
    return raw


def research(store: LocalStorage, ref: Any) -> list[dict[str, Any]] | None:
    entries: list[dict[str, Any]] | None = rq.read_research(store, ref)
    return entries


# S3 (amended in planning S3: «поле `deep_question` — … в схемі фасилітатора під роутером і в
# `RouterAnswer`»):
# without the router the card's schema has no such field; under it — the field, and the cycle follows
def test_deep_question_only_under_the_router_and_the_one_cycle_runs_from_the_card_and_from_answer(
    tmp_path: Path,
) -> None:
    plain = rdp.deep_llm(streams=[rdp.Stream([PLAIN_REPLY], card_raw(PLAIN_REPLY))])
    list(respond(rq.context(routing=None), rq.knowledge(), plain))
    assert "deep_question" not in plain.of("stream")[0].schema.model_fields
    assert "deep_question" in router_schema(fa.knowledge()).model_fields

    # from the card (lead) under the router
    store = LocalStorage(tmp_path / "card")
    ref = rq.topic(store)
    rq.put_routing(store, ref, [rq.d_choose(1, "alpha")])
    llm = rdp.full_deep(
        streams=[rdp.Stream(["Досліджую глибше."], card_raw("Досліджую глибше.", deep_question=rdp.DQ))]
    )
    got, _ = say(store, facilitate(llm), ref, "Так, досліди.")
    assert isinstance(got[-1], Answered), got[-1]
    assert "deep_question" in llm.of("stream")[0].schema.model_fields
    assert [c.kind for c in llm.calls if c.kind != "search"] == ["stream", "plan", "report"]
    assert research(store, ref) == [deep_entry(2)]
    facts = [i for i in rq.read_map(store, ref)["items"] if i["type"] == "fact"]
    assert sorted(i["text"] for i in facts) == sorted([rdp.FACT_1, rdp.FACT_2])

    # from the router's «answer»
    store = LocalStorage(tmp_path / "answer")
    ref = rq.topic(store)
    llm = rdp.full_deep(router=[rdp.with_deep_question(fa.answer_raw(), rdp.DQ)])
    got, _ = say(store, facilitate(llm, fa.knowledge()), ref, "Так, досліди глибоко.")
    assert isinstance(got[-1], Answered), got[-1]
    assert [c.kind for c in llm.calls if c.kind != "search"] == ["router", "plan", "report"]
    assert research(store, ref) == [deep_entry(2)]
    facts = [i for i in rq.read_map(store, ref)["items"] if i["type"] == "fact"]
    assert sorted(i["text"] for i in facts) == sorted([rdp.FACT_1, rdp.FACT_2])
