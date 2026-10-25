"""Contract tests of research-quick, `workspace`: shown = recorded through `workspace.reply` (Seam 3) and
`research.json` appended by the number of the model's answer (Seam 5) (slice tester; from the contract)."""

from collections.abc import Sequence
from functools import partial
from pathlib import Path
from typing import Any

from pydantic import BaseModel
from rq_fakes import (
    ALICE,
    T0,
    Down,
    ScenarioFacilitate,
    answer,
    d_choose,
    knowledge,
    put_routing,
    raw_research,
    read_research,
    topic,
    upd,
    update_only,
)

from thinkhow.facilitation import ReplyDelta, ResearchEvent, respond
from thinkhow.facilitation.types import Source
from thinkhow.platform import llm as pl
from thinkhow.platform.storage import LocalStorage
from thinkhow.workspace import Answered, Delta, Failed, open_topic, reply

REPLY = "Оренда офісу в Лейпцигу коштує від 15 євро за метр. Скільки метрів вам треба?"
FOUND = pl.Found(
    ("оренда офісу Лейпциг ціна",),
    (pl.Source("Ціни оренди", "https://a.example/rent"), pl.Source("Ринок", "https://b.example/m")),
    None,
)
LINE = "\n\nДжерела: [Ціни оренди](https://a.example/rent), [Ринок](https://b.example/m)"
PERSON = "Не знаю, скільки коштує оренда офісу."


def scripted(store: LocalStorage, full: str, found: pl.Found | None) -> Any:
    def script(system: str, contents: Sequence[pl.Turn], schema: type[BaseModel]) -> str:
        return full if "reply" in schema.model_fields else update_only("a_two")

    def found_script(system: str, contents: Sequence[pl.Turn], schema: type[BaseModel]) -> pl.Found | None:
        return found

    llm = pl.ScriptedLlm(script, found_script=found_script)
    return partial(respond, knowledge=knowledge(), llm=llm)


def shown_and_recorded(store: LocalStorage, fac: Any) -> tuple[str, str, list[Any]]:
    ref = topic(store)
    put_routing(store, ref, [d_choose(1, "alpha")])
    got = list(reply(store, fac, ALICE, ref, PERSON, T0))
    assert isinstance(got[-1], Answered), got[-1]
    shown = "".join(e.text for e in got if isinstance(e, Delta))
    recorded = open_topic(store, ALICE, ref, T0).sessions[-1].turns[-1].text
    return shown, recorded, read_research(store, ref) or []


def test_seam3_the_streamed_text_equals_the_recorded_answer_and_ends_with_the_sources_line(
    tmp_path: Path,
) -> None:
    cases = {
        "valid stream": answer(REPLY, "a_one"),
        "invalid stream with shown text (settle)": answer(REPLY, "b_one"),
    }
    for i, (name, full) in enumerate(cases.items()):
        store = LocalStorage(tmp_path / str(i))
        shown, recorded, _ = shown_and_recorded(store, scripted(store, full, FOUND))
        assert shown == recorded, name
        assert recorded == REPLY + LINE, name


def entry(turn: int, ev: ResearchEvent) -> dict[str, Any]:
    return {
        "turn": turn,
        "depth": ev.depth,
        "queries": list(ev.queries),
        "sources": [{"title": s.title, "url": s.url} for s in ev.sources],
        "suggestions_html": ev.suggestions_html,
        "question": ev.question,
        "report": ev.report,
    }


EV_A = ResearchEvent(
    depth="quick",
    queries=("оренда офісу Лейпциг",),
    sources=(Source("Ціни оренди", "https://a.example/rent"),),
    suggestions_html="<div>a</div>",
)
EV_B = ResearchEvent(
    depth="quick",
    queries=("кава Лейпциг ціна", "кав'ярні Лейпциг"),
    sources=(Source("Кава", "https://c.example/coffee"), Source("Ринок", "https://b.example/m")),
    suggestions_html=None,
)


def test_seam5_research_json_gets_one_entry_per_searched_answer_by_the_model_answer_number(
    tmp_path: Path,
) -> None:
    store = LocalStorage(tmp_path)
    ref = topic(store)
    fac = ScenarioFacilitate(
        [
            [ReplyDelta("Від 15 євро."), EV_A, upd("Від 15 євро.")],
            [ReplyDelta("Що для вас важливо?"), upd("Що для вас важливо?")],
            [ReplyDelta("Кава — 3 євро."), EV_B, upd("Кава — 3 євро.")],
        ]
    )
    assert isinstance(list(reply(store, fac, ALICE, ref, "Скільки коштує оренда?", T0))[-1], Answered)
    assert read_research(store, ref) == [entry(2, EV_A)]
    before = raw_research(store, ref)
    got = list(reply(store, fac, ALICE, ref, "Мені важливо місце.", T0))
    assert isinstance(got[-1], Answered)
    assert raw_research(store, ref) == before
    got = list(reply(store, fac, ALICE, ref, "А скільки коштує кава?", T0))
    assert isinstance(got[-1], Answered)
    assert [e.text for e in got if isinstance(e, Delta)] == ["Кава — 3 євро."]
    assert read_research(store, ref) == [entry(2, EV_A), entry(6, EV_B)]


def test_seam5_failed_after_a_research_event_writes_no_research_json(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    ref = topic(store)
    fac = ScenarioFacilitate([[EV_A, ReplyDelta("Від"), Down("down")]])
    got = list(reply(store, fac, ALICE, ref, "Скільки коштує оренда?", T0))
    assert isinstance(got[-1], Failed)
    assert raw_research(store, ref) is None
    # the same answer without the failure does write it: the event itself reaches research.json
    store2 = LocalStorage(tmp_path / "ok")
    ref2 = topic(store2)
    fac2 = ScenarioFacilitate([[EV_A, ReplyDelta("Від 15."), upd("Від 15.")]])
    assert isinstance(list(reply(store2, fac2, ALICE, ref2, "Скільки коштує оренда?", T0))[-1], Answered)
    assert read_research(store2, ref2) == [entry(2, EV_A)]


def test_seam5_through_the_real_chain_and_queries_without_sources_give_an_entry_without_a_line(
    tmp_path: Path,
) -> None:
    store = LocalStorage(tmp_path / "sources")
    shown, recorded, entries = shown_and_recorded(store, scripted(store, answer(REPLY, "a_one"), FOUND))
    assert recorded == REPLY + LINE
    assert [set(e) for e in entries] == [
        {"turn", "depth", "queries", "sources", "suggestions_html", "question", "report"}
    ]
    # `question` and `report` of a quick search are not fixed by the contract (question Q4): not compared
    assert [{k: v for k, v in e.items() if k not in ("question", "report")} for e in entries] == [
        {
            "turn": 2,
            "depth": "quick",
            "queries": ["оренда офісу Лейпциг ціна"],
            "sources": [
                {"title": "Ціни оренди", "url": "https://a.example/rent"},
                {"title": "Ринок", "url": "https://b.example/m"},
            ],
            "suggestions_html": None,
        }
    ]

    store = LocalStorage(tmp_path / "queries")
    only_queries = pl.Found(("оренда офісу Лейпциг ціна",), (), None)
    shown, recorded, entries = shown_and_recorded(
        store, scripted(store, answer(REPLY, "a_one"), only_queries)
    )
    assert shown == recorded == REPLY
    assert "Джерела:" not in recorded
    assert len(entries) == 1
    assert entries[0]["turn"] == 2
    assert entries[0]["queries"] == ["оренда офісу Лейпциг ціна"]
    assert entries[0]["sources"] == []
