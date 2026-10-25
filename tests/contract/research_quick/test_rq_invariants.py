"""Contract tests of research-quick: the invariants I1-I5 (slice tester; inputs chosen by hand from each
«Domain», expected values written by hand)."""

from pathlib import Path
from typing import Any

import google.genai.types as gt
from rq_fakes import (
    ALICE,
    ROUTED,
    T0,
    Down,
    FoundLlm,
    Piece,
    ScenarioFacilitate,
    answer,
    context,
    has_search_tool,
    knowledge,
    meta,
    no_tools,
    raw_research,
    read_research,
    split_chunks,
    topic,
    upd,
    update_only,
    vertex,
    web,
)

from thinkhow.facilitation import FacilitatorUpdate, ReplyDelta, ResearchEvent, respond
from thinkhow.facilitation.respond import answer_schema, lead
from thinkhow.facilitation.types import Source
from thinkhow.platform import llm as pl
from thinkhow.platform.storage import LocalStorage
from thinkhow.workspace import Answered, Failed, reply, retry

REPLY = "Оренда в Лейпцигу коштує від 15 євро за метр. Скільки метрів вам треба?"
DELTAS = ["Оренда в Лейпцигу коштує ", "від 15 євро за метр. ", "Скільки метрів вам треба?"]
WITH_SOURCES = pl.Found(
    ("оренда Лейпциг",),
    (pl.Source("[Звіт] оренди", "https://a.example/rent(2026)"), pl.Source("Ринок", "https://b.example/m")),
    None,
)
LINE = "\n\nДжерела: [Звіт оренди](https://a.example/rent%282026%29), [Ринок](https://b.example/m)"
ONLY_QUERIES = pl.Found(("оренда Лейпциг", "ціни офісів"), (), None)


def reply_last(text: str, phase: str) -> str:
    return (
        '{"current_phase_id": "'
        + phase
        + '", "phase_exit_met": false, "map_updates": [], "reply": "'
        + text
        + '"}'
    )


def streams() -> dict[str, tuple[list[str], str, list[str]]]:
    """(deltas, the raw JSON of Done, what generate_json answers): every path of `_settle`."""
    return {
        "valid with deltas": (list(DELTAS), answer(REPLY, "a_one"), []),
        "valid without deltas": ([], reply_last(REPLY, "a_one"), []),
        "invalid with deltas": (list(DELTAS), answer(REPLY, "b_one"), [update_only("a_two")]),
        "invalid without deltas": (
            [],
            '{"current_phase_id": "a_one", "phase_exit_met": fal',
            [answer(REPLY)],
        ),
    }


def shown_and_update(items: list[Any]) -> tuple[str, FacilitatorUpdate]:
    updates = [i for i in items if isinstance(i, FacilitatorUpdate)]
    assert len(updates) == 1
    return "".join(i.text for i in items if isinstance(i, ReplyDelta)), updates[0]


# ------------------------------------------------------------------ I1


def test_I1_the_streamed_text_equals_the_recorded_reply_on_every_path() -> None:
    for name, (deltas, raw, generate) in streams().items():
        for found, tail in ((None, ""), (WITH_SOURCES, LINE), (ONLY_QUERIES, "")):
            for call in ("lead", "respond under the router"):
                llm = FoundLlm(deltas=list(deltas), done_raw=raw, found=found, generate=list(generate))
                items: list[Any]
                if call == "lead":
                    items = list(lead(context(), knowledge(), llm))
                else:
                    items = list(respond(context(routing=ROUTED), knowledge(), llm))
                shown, update = shown_and_update(items)
                case = (name, found is not None and bool(found.sources), call)
                assert shown == update.reply, case
                assert update.reply == REPLY + tail, case


# ------------------------------------------------------------------ I2 (keeps: as before the slice)


def test_I2_without_found_lead_gives_the_same_events_as_before_the_slice() -> None:
    exact: list[tuple[list[str], str, list[str], list[Any]]] = [
        (
            list(DELTAS),
            answer(REPLY, "a_one"),
            [],
            [
                *(ReplyDelta(d) for d in DELTAS),
                FacilitatorUpdate(
                    reply=REPLY, current_phase_id="a_one", phase_exit_met=False, map_updates=[]
                ),
            ],
        ),
        (
            list(DELTAS),
            answer(REPLY, "b_one"),
            [update_only("a_two")],
            [
                *(ReplyDelta(d) for d in DELTAS),
                FacilitatorUpdate(
                    reply=REPLY, current_phase_id="a_two", phase_exit_met=False, map_updates=[]
                ),
            ],
        ),
    ]
    for deltas, raw, generate, want in exact:
        for routing in (ROUTED, None):
            llm = FoundLlm(deltas=deltas, done_raw=raw, generate=list(generate))
            assert list(lead(context(routing=routing), knowledge(), llm)) == want
    for name, (deltas, raw, generate) in streams().items():
        for call in ("lead", "respond under the router", "respond without the router"):
            llm = FoundLlm(deltas=list(deltas), done_raw=raw, generate=list(generate))
            items: list[Any]
            if call == "lead":
                items = list(lead(context(), knowledge(), llm))
            elif call == "respond under the router":
                items = list(respond(context(routing=ROUTED), knowledge(), llm))
            else:
                items = list(respond(context(routing=None), knowledge(), llm))
            assert not [i for i in items if isinstance(i, ResearchEvent)], (name, call)
            assert not [i for i in items if isinstance(i, ReplyDelta) and "Джерела" in i.text], (name, call)
            shown, update = shown_and_update(items)
            assert update.reply == REPLY and "Джерела" not in update.reply, (name, call)
            assert isinstance(items[-1], FacilitatorUpdate) or call == "respond under the router", (
                name,
                call,
            )


# ------------------------------------------------------------------ I3


def test_I3_the_sources_line_holds_every_url_once_in_first_appearance_order_however_chunks_carry_them() -> (
    None
):
    raw = answer(REPLY, "a_one")
    pieces = split_chunks(raw, 4)
    a = web("https://a.example/rent(2026)", "[Звіт] оренди")
    b = web("https://b.example/x", None, "b.example")
    c = web("https://c.example/y", None, None)
    no_web = gt.GroundingChunk(
        retrieved_context=gt.GroundingChunkRetrievedContext(uri="https://r.example", title="R")
    )
    line = (
        "\n\nДжерела: [Звіт оренди](https://a.example/rent%282026%29), [b.example](https://b.example/x), "
        "[https://c.example/y](https://c.example/y)"
    )
    full = meta(["оренда Лейпциг"], [a, b, no_web, c])
    plans: dict[str, list[Any]] = {
        "parts and repeats": [
            Piece(pieces[0], meta(["оренда Лейпциг"], [a])),
            Piece(pieces[1], meta(None, [b, no_web])),
            Piece(pieces[2], meta(["оренда Лейпциг"], [a, c])),
            Piece(pieces[3], meta(None, [b])),
        ],
        "the same full metadata in every chunk": [Piece(p, full) for p in pieces],
        "all in the last chunk": [Piece(p) for p in pieces[:3]] + [Piece(pieces[3], full)],
    }
    for name, plan in plans.items():
        llm, _ = vertex([plan], search=True)
        items = list(lead(context(), knowledge(), llm))
        shown, update = shown_and_update(items)
        assert update.reply == REPLY + line, name
        assert shown == update.reply, name
        for url in ("https://a.example/rent%282026%29", "https://b.example/x", "https://c.example/y"):
            assert update.reply.count(f"]({url})") == 1, (name, url)
        (ev,) = [i for i in items if isinstance(i, ResearchEvent)]
        assert ev.sources == (
            Source("[Звіт] оренди", "https://a.example/rent(2026)"),
            Source("b.example", "https://b.example/x"),
            Source("https://c.example/y", "https://c.example/y"),
        ), name


# ------------------------------------------------------------------ I4


def test_I4_generate_json_never_passes_the_search_tool() -> None:
    schemas: list[Any] = [answer_schema(knowledge().cards["alpha"]), FacilitatorUpdate]
    ok = answer(REPLY, "a_one")
    for search in (True, False):
        for schema in schemas:
            llm, client = vertex([[ok]], search=search)
            llm.generate_json("sys", [pl.Turn("user", "Скільки коштує оренда?")], schema, None)
            assert no_tools(client.calls[0]), (search, schema)
    # after a searched stream on the same instance
    llm, client = vertex([[ok], [ok]], search=True)
    list(llm.stream_json("sys", [pl.Turn("user", "Скільки коштує оренда?")], schemas[0], None))
    llm.generate_json("sys", [pl.Turn("user", "Скільки коштує оренда?")], schemas[0], None)
    assert has_search_tool(client.calls[0])
    assert no_tools(client.calls[1])
    # the settle retry of lead, with a found in the stream: the retry asks without the tool
    bad = answer(REPLY, "b_one")
    gm = meta(["оренда Лейпциг"], [web("https://b.example/m", "Ринок")])
    llm, client = vertex([[Piece(p, gm) for p in split_chunks(bad, 3)], [update_only("a_two")]], search=True)
    items = list(lead(context(), knowledge(), llm))
    assert client.models.kinds == ["stream", "generate"]
    assert has_search_tool(client.calls[0])
    assert no_tools(client.calls[1])
    _, update = shown_and_update(items)
    assert update.reply == REPLY + "\n\nДжерела: [Ринок](https://b.example/m)"


# ------------------------------------------------------------------ I5


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


DEEP = ResearchEvent(
    depth="deep",
    queries=("ринок кав'ярень Лейпциг",),
    sources=(Source("Ринок кави", "https://k.example/r"),),
    suggestions_html=None,
    question="Скільки кав'ярень у центрі Лейпцига?",
    report="Близько 40 кав'ярень.",
)
QUICK_1 = ResearchEvent(depth="quick", queries=("оренда",), sources=(), suggestions_html="<div>1</div>")
QUICK_2 = ResearchEvent(
    depth="quick",
    queries=("ціни кави",),
    sources=(Source("Кава", "https://c.example/coffee"),),
    suggestions_html=None,
)
QUICK_3 = ResearchEvent(
    depth="quick",
    queries=("персонал",),
    sources=(Source("Зарплати", "https://z.example/s"),),
    suggestions_html=None,
)


def test_I5_research_json_only_grows_and_each_entry_has_the_number_of_its_model_answer(
    tmp_path: Path,
) -> None:
    store = LocalStorage(tmp_path)
    ref = topic(store)
    fac = ScenarioFacilitate(
        [
            [DEEP, ReplyDelta("Близько 40."), upd("Близько 40.")],  # answer 2
            [ReplyDelta("Що далі?"), upd("Що далі?")],  # answer 4, no research
            [
                QUICK_1,
                QUICK_2,
                ReplyDelta("Від 15 і 3 євро."),
                upd("Від 15 і 3 євро."),
            ],  # answer 6, two events
            [QUICK_3, ReplyDelta("Зарп"), Down("down")],  # turn 7 fails
            [QUICK_3, ReplyDelta("Від 2000 євро."), upd("Від 2000 євро.")],  # its retry: answer 8
        ]
    )
    assert isinstance(list(reply(store, fac, ALICE, ref, "Скільки кав'ярень у центрі?", T0))[-1], Answered)
    first = read_research(store, ref)
    assert first == [entry(2, DEEP)]
    before = raw_research(store, ref)
    assert isinstance(list(reply(store, fac, ALICE, ref, "Добре.", T0))[-1], Answered)
    assert raw_research(store, ref) == before
    assert isinstance(list(reply(store, fac, ALICE, ref, "А оренда і кава?", T0))[-1], Answered)
    assert read_research(store, ref) == [entry(2, DEEP), entry(6, QUICK_1), entry(6, QUICK_2)]
    after_six = raw_research(store, ref)
    assert isinstance(list(reply(store, fac, ALICE, ref, "А персонал?", T0))[-1], Failed)
    assert raw_research(store, ref) == after_six
    assert isinstance(list(retry(store, fac, ALICE, ref, T0))[-1], Answered)
    assert read_research(store, ref) == [
        entry(2, DEEP),
        entry(6, QUICK_1),
        entry(6, QUICK_2),
        entry(8, QUICK_3),
    ]
