"""Contract tests of research-deep through `workspace.reply`: deep research under the card, the whole way
(Seam 1, with `ScriptedLlm`), on the router's path (Seam 2), and every search failed (Seam 3)
(slice tester; from the contract).

Superseded by deep-research-confirm-first: the reply that decides on deep research writes a proposal
(`deep_pending.json`) and searches nothing; the cycle and its writes come on the person's next turn when they
agree («yes»)."""

from collections.abc import Sequence
from functools import partial
from pathlib import Path
from typing import Any

from pydantic import BaseModel
from rdp_fakes import (
    DQ,
    FACT_1,
    FACT_2,
    LINE_ABC,
    PROPOSAL_ABC,
    QUERIES_ABC,
    REPORT,
    SEARCHES_ABC,
    STEPS_ABC,
    card_answer,
    card_update,
    consent_raw,
    fa,
    full_deep,
    plan_raw,
    report_raw,
    rq,
    with_deep_question,
)

from thinkhow.facilitation import respond
from thinkhow.facilitation.types import (
    DeepConsent,
    DeepPlan,
    DeepReport,
    FacilitatorUpdate,
    MapUpdate,
    ReplyDelta,
)
from thinkhow.platform import llm as pl
from thinkhow.platform.storage import LocalStorage
from thinkhow.workspace import Answered, Delta, Failed, open_topic, reply
from thinkhow.workspace.conversation import normalize

FIRST = "Звучить як питання ринку. Досліджую глибше."
FOUND_1 = pl.Found(("Mittelstand Beratung",), (pl.Source("Перше джерело", "https://q.example/first"),), None)
LINE_1 = "\n\nДжерела: [Перше джерело](https://q.example/first)"
SEED = "Кому саме ви хочете продавати?"
GOAL = {"id": "d5-1", "type": "goal", "text": "продавати консалтинг Mittelstand", "turn": "t1"}
PENDING = "deep_pending.json"
SOURCES_ABC = [
    {"title": "Mittelstand Studie", "url": "https://a.example/mittelstand"},
    {"title": "Beratermarkt", "url": "https://b.example/markt"},
    {"title": "IHK Leipzig", "url": "https://c.example/ihk"},
]


def deep_entry(turn: int) -> dict[str, Any]:
    return {
        "turn": turn,
        "depth": "deep",
        "queries": list(QUERIES_ABC),
        "sources": SOURCES_ABC,
        "suggestions_html": "<div>підказки Б</div>",
        "question": DQ,
        "report": REPORT,
    }


def say(store: LocalStorage, fac: Any, ref: Any, text: str) -> tuple[list[Any], str]:
    got = list(reply(store, fac, rq.ALICE, ref, text, rq.T0))
    return got, "".join(e.text for e in got if isinstance(e, Delta))


def recorded(store: LocalStorage, ref: Any) -> str:
    return open_topic(store, rq.ALICE, ref, rq.T0).sessions[-1].turns[-1].text


def scripted() -> pl.ScriptedLlm:
    def script(system: str, contents: Sequence[pl.Turn], schema: type[BaseModel]) -> str:
        fields = schema.model_fields
        if issubclass(schema, DeepPlan):
            return plan_raw()
        if issubclass(schema, DeepReport):
            return report_raw()
        if issubclass(schema, DeepConsent):
            return consent_raw("yes")
        if "reply" in fields:
            if "deep_question" in fields:
                return card_answer(FIRST, "b_two", True, [], deep_question=DQ)
            return card_answer(FIRST, "b_two", True, [])
        return card_update("b_two")

    def found_script(system: str, contents: Sequence[pl.Turn], schema: type[BaseModel]) -> pl.Found | None:
        return FOUND_1 if "reply" in schema.model_fields else None

    def search_script(system: str, prompt: str) -> tuple[str, pl.Found | None]:
        answer: tuple[str, pl.Found | None] = SEARCHES_ABC[prompt]
        return answer

    return pl.ScriptedLlm(script, found_script=found_script, search_script=search_script)


def test_seam1_deep_under_the_card_through_workspace_writes_the_shown_text_research_map_and_the_card_end(
    tmp_path: Path,
) -> None:
    store = LocalStorage(tmp_path)
    ref = rq.topic(store)
    rq.put_routing(store, ref, [rq.d_choose(1, "beta")])
    seed = FacilitatorUpdate(
        reply=SEED,
        current_phase_id="b_one",
        phase_exit_met=False,
        map_updates=[MapUpdate.model_validate({"op": "add", **GOAL})],
    )
    got, _ = say(store, rq.ScenarioFacilitate([[ReplyDelta(SEED), seed]]), ref, "Хочу продавати консалтинг.")
    assert isinstance(got[-1], Answered)
    fac = partial(respond, knowledge=rq.knowledge(), llm=scripted())

    # the reply that decides on deep research: the card's answer, its sources line, then the proposal
    got, shown = say(store, fac, ref, "Досліди це глибоко.")
    assert isinstance(got[-1], Answered), got[-1]
    assert shown.startswith(FIRST + LINE_1) and shown.endswith(PROPOSAL_ABC)
    assert shown[len(FIRST + LINE_1) : -len(PROPOSAL_ABC)].strip() == ""
    assert recorded(store, ref) == normalize(shown)
    assert store.read("users", rq.topic_path(ref, PENDING)) is not None
    entries = rq.read_research(store, ref)
    assert entries is not None and [(e["turn"], e["depth"]) for e in entries] == [(4, "quick")]
    routing = fa.read_routing(store, ref)
    assert routing is not None
    assert (routing[-1].kind, routing[-1].end, routing[-1].card_id) == ("end", "done", "beta")

    # the person agrees: the cycle over the shown sub-questions
    got, shown = say(store, fac, ref, "Так, запускай.")
    assert isinstance(got[-1], Answered), got[-1]
    assert shown == STEPS_ABC + "\n\n" + REPORT + LINE_ABC
    assert recorded(store, ref) == normalize(shown)

    entries = rq.read_research(store, ref)
    assert entries is not None and len(entries) == 2
    assert (entries[0]["turn"], entries[0]["depth"]) == (4, "quick")
    assert entries[0]["sources"] == [{"title": "Перше джерело", "url": "https://q.example/first"}]
    assert entries[1] == deep_entry(6)

    items = rq.read_map(store, ref)["items"]
    assert GOAL in items
    assert {"id": "d5-2", "type": "fact", "text": FACT_1, "turn": "t5"} in items
    assert {"id": "d5-3", "type": "fact", "text": FACT_2, "turn": "t5"} in items
    assert len(items) == 3
    assert store.read("users", rq.topic_path(ref, PENDING)) is None


def test_seam2_deep_on_the_router_path_through_workspace_writes_routing_research_map_and_the_shown_text(
    tmp_path: Path,
) -> None:
    store = LocalStorage(tmp_path)
    ref = rq.topic(store)
    llm = full_deep(router=[with_deep_question(fa.answer_raw(), DQ)], consents=[consent_raw("yes")])
    fac = partial(respond, knowledge=fa.knowledge(), llm=llm)
    got, shown = say(store, fac, ref, "Досліди глибоко.")
    assert isinstance(got[-1], Answered), got[-1]
    assert shown == PROPOSAL_ABC
    assert llm.of("search") == [] and llm.of("report") == []
    assert rq.read_research(store, ref) is None

    got, shown = say(store, fac, ref, "Так.")
    assert isinstance(got[-1], Answered), got[-1]
    assert shown == STEPS_ABC + "\n\n" + REPORT + LINE_ABC
    assert recorded(store, ref) == normalize(shown)
    assert fa.ROUTER_REPLY not in shown
    assert llm.of("stream") == []
    routing = fa.read_routing(store, ref)
    assert routing is not None and [(d.kind, d.turn) for d in routing] == [("answer", 1)]
    assert rq.read_research(store, ref) == [deep_entry(4)]
    items = rq.read_map(store, ref)["items"]
    assert {"id": "d3-1", "type": "fact", "text": FACT_1, "turn": "t3"} in items
    assert {"id": "d3-2", "type": "fact", "text": FACT_2, "turn": "t3"} in items


def test_seam3_every_search_failed_is_failed_and_no_file_changes_but_the_turn_of_the_person(
    tmp_path: Path,
) -> None:
    store = LocalStorage(tmp_path)
    ref = rq.topic(store)
    down = pl.LlmUnavailable("search down")
    llm = full_deep(router=[with_deep_question(fa.answer_raw(), DQ)], consents=[consent_raw("yes")])
    llm.searches = {q: down for q in SEARCHES_ABC}
    fac = partial(respond, knowledge=fa.knowledge(), llm=llm)
    got, _ = say(store, fac, ref, "Досліди глибоко.")
    assert isinstance(got[-1], Answered), got[-1]
    names = ("map.json", "routing.json", "research.json", PENDING)
    before = {n: store.read("users", rq.topic_path(ref, n)) for n in names}
    got, _ = say(store, fac, ref, "Так.")
    assert isinstance(got[-1], Failed), got[-1]
    assert len(llm.of("search")) == 3
    assert llm.of("report") == []
    assert {n: store.read("users", rq.topic_path(ref, n)) for n in names} == before
    turns = [t for s in open_topic(store, rq.ALICE, ref, rq.T0).sessions for t in s.turns]
    assert [(t.role, t.text) for t in turns] == [
        ("user", "Досліди глибоко."),
        ("model", PROPOSAL_ABC),
        ("user", "Так."),
    ]
