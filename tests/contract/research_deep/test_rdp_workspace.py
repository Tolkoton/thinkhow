"""Contract tests of research-deep through `workspace.reply`: deep research under the card, the whole way
(Seam 1, with `ScriptedLlm`), on the router's path (Seam 2), and every search failed (Seam 3)
(slice tester; from the contract)."""

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
    QUERIES_ABC,
    REPORT,
    SEARCHES_ABC,
    card_answer,
    card_update,
    fa,
    full_deep,
    plan_raw,
    report_raw,
    rq,
    steps_lines,
    want_steps,
    with_deep_question,
)

from thinkhow.facilitation import respond
from thinkhow.facilitation.types import DeepPlan, DeepReport, FacilitatorUpdate, MapUpdate, ReplyDelta
from thinkhow.platform import llm as pl
from thinkhow.platform.storage import LocalStorage
from thinkhow.workspace import Answered, Delta, Failed, open_topic, reply
from thinkhow.workspace.conversation import normalize

FIRST = "Звучить як питання ринку. Досліджую глибше."
FOUND_1 = pl.Found(("Mittelstand Beratung",), (pl.Source("Перше джерело", "https://q.example/first"),), None)
LINE_1 = "\n\nДжерела: [Перше джерело](https://q.example/first)"
SEED = "Кому саме ви хочете продавати?"
GOAL = {"id": "d3-1", "type": "goal", "text": "продавати консалтинг Mittelstand", "turn": "t1"}
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

    got, shown = say(store, partial(respond, knowledge=rq.knowledge(), llm=scripted()), ref, "Так, досліди.")
    assert isinstance(got[-1], Answered), got[-1]
    head, tail = FIRST + LINE_1 + "\n\n", "\n\n" + REPORT + LINE_ABC
    assert shown.startswith(head) and shown.endswith(tail)
    assert steps_lines(shown[len(head) : -len(tail)]) == want_steps()
    assert recorded(store, ref) == normalize(shown)

    entries = rq.read_research(store, ref)
    assert entries is not None and len(entries) == 2
    assert (entries[0]["turn"], entries[0]["depth"]) == (4, "quick")
    assert entries[0]["sources"] == [{"title": "Перше джерело", "url": "https://q.example/first"}]
    assert entries[1] == deep_entry(4)

    items = rq.read_map(store, ref)["items"]
    assert GOAL in items
    assert {"id": "d3-2", "type": "fact", "text": FACT_1, "turn": "t3"} in items
    assert {"id": "d3-3", "type": "fact", "text": FACT_2, "turn": "t3"} in items
    assert len(items) == 3

    routing = fa.read_routing(store, ref)
    assert routing is not None
    assert (routing[-1].kind, routing[-1].end, routing[-1].card_id) == ("end", "done", "beta")


def test_seam2_deep_on_the_router_path_through_workspace_writes_routing_research_map_and_the_shown_text(
    tmp_path: Path,
) -> None:
    store = LocalStorage(tmp_path)
    ref = rq.topic(store)
    llm = full_deep(router=[with_deep_question(fa.answer_raw(), DQ)])
    got, shown = say(store, partial(respond, knowledge=fa.knowledge(), llm=llm), ref, "Так, досліди глибоко.")
    assert isinstance(got[-1], Answered), got[-1]
    assert shown.endswith("\n\n" + REPORT + LINE_ABC)
    assert steps_lines(shown[: -len("\n\n" + REPORT + LINE_ABC)]) == want_steps()
    assert recorded(store, ref) == normalize(shown)
    assert fa.ROUTER_REPLY not in shown
    assert llm.of("stream") == []
    routing = fa.read_routing(store, ref)
    assert routing is not None and [(d.kind, d.turn) for d in routing] == [("answer", 1)]
    assert rq.read_research(store, ref) == [deep_entry(2)]
    items = rq.read_map(store, ref)["items"]
    assert {"id": "d1-1", "type": "fact", "text": FACT_1, "turn": "t1"} in items
    assert {"id": "d1-2", "type": "fact", "text": FACT_2, "turn": "t1"} in items


def test_seam3_every_search_failed_is_failed_and_no_file_changes_but_the_turn_of_the_person(
    tmp_path: Path,
) -> None:
    store = LocalStorage(tmp_path)
    ref = rq.topic(store)
    names = ("map.json", "routing.json", "research.json")
    before = {n: store.read("users", rq.topic_path(ref, n)) for n in names}
    down = pl.LlmUnavailable("search down")
    llm = full_deep(router=[with_deep_question(fa.answer_raw(), DQ)])
    llm.searches = {q: down for q in SEARCHES_ABC}
    got, _ = say(store, partial(respond, knowledge=fa.knowledge(), llm=llm), ref, "Так, досліди глибоко.")
    assert isinstance(got[-1], Failed), got[-1]
    assert len(llm.of("search")) == 3
    assert llm.of("report") == []
    assert {n: store.read("users", rq.topic_path(ref, n)) for n in names} == before
    turns = [t for s in open_topic(store, rq.ALICE, ref, rq.T0).sessions for t in s.turns]
    assert [(t.role, t.text) for t in turns] == [("user", "Так, досліди глибоко.")]
