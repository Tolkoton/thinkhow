"""Contract tests of research-deep: the invariants I1-I4 (slice tester; inputs chosen by hand from each
«Domain», expected values written by hand)."""

import time
from functools import partial
from pathlib import Path
from typing import Any

from rdp_fakes import (
    DQ,
    FACT_1,
    FACT_2,
    LINK_A,
    LINK_B,
    LINK_C,
    LINK_D,
    PA,
    PB,
    PC,
    PD,
    QA,
    QB,
    QC,
    QD,
    REPORT,
    SA,
    SB,
    SC,
    SD,
    TEXT_A,
    TEXT_B,
    TEXT_C,
    TEXT_D,
    Stream,
    card_answer,
    ctx,
    deep_llm,
    fa,
    fact_update,
    full_deep,
    plan_raw,
    report_raw,
    rq,
    with_deep_question,
)

from thinkhow.facilitation import FacilitatorUpdate, ReplyDelta, ResearchEvent, converse, respond
from thinkhow.facilitation.deep import DeepDone, deep_research, with_deep
from thinkhow.facilitation.types import FactAnswer, MapItem, MapUpdate, Source
from thinkhow.platform import llm as pl
from thinkhow.platform.storage import LocalStorage
from thinkhow.workspace import Answered, Delta, open_topic, reply
from thinkhow.workspace.conversation import normalize

REV = pl.KnowledgeRev(rev=3, n=7)
REPLY = "Звучить як питання ринку. Можу дослідити глибше."
DELTAS = ["Звучить як питання ринку. ", "Можу дослідити глибше."]
FOUND_1 = pl.Found(("Mittelstand Beratung",), (pl.Source("Перше джерело", "https://q.example/first"),), None)
LINE_1 = "\n\nДжерела: [Перше джерело](https://q.example/first)"
DOWN = pl.LlmUnavailable("search down")


def found(*sources: pl.Source) -> pl.Found:
    return pl.Found((f"запит {len(sources)}",), tuple(sources), None)


def str_or_none(value: str | None) -> str | None:
    return value


def done_of(items: list[Any]) -> DeepDone:
    assert isinstance(items[-1], DeepDone), items[-1]
    return items[-1]


# ------------------------------------------------------------------ I1


def test_I1_the_text_shown_by_the_stream_equals_the_recorded_answer_with_deep_research(
    tmp_path: Path,
) -> None:
    card_raw = card_answer(REPLY, "a_one", deep_question=DQ)
    cases: dict[str, tuple[str, Any, str]] = {
        "card, first found, 3 sub-questions, none failed": (
            "card",
            full_deep(streams=[Stream(list(DELTAS), card_raw, FOUND_1)]),
            "\n\n" + REPORT + "\n\nДжерела: " + ", ".join([LINK_A, LINK_B, LINK_C]),
        ),
        "card, no first found, 2 sub-questions, one failed": (
            "card",
            deep_llm(
                [plan_raw(questions=[QA, QB])],
                [report_raw()],
                {QA: DOWN, QB: (TEXT_B, found(PB))},
                streams=[Stream(list(DELTAS), card_raw, None)],
            ),
            "\n\n" + REPORT + "\n\nДжерела: " + LINK_B,
        ),
        "router, 4 sub-questions, two failed": (
            "router",
            deep_llm(
                [plan_raw(questions=[QA, QB, QC, QD])],
                [report_raw()],
                {QA: DOWN, QB: (TEXT_B, found(PB)), QC: DOWN, QD: (TEXT_D, found(PD, PB))},
                router=[with_deep_question(fa.answer_raw(), DQ)],
            ),
            "\n\n" + REPORT + "\n\nДжерела: " + ", ".join([LINK_B, LINK_D]),
        ),
        "router, 2 sub-questions, nothing among the sources": (
            "router",
            deep_llm(
                [plan_raw(questions=[QA, QB])],
                [report_raw()],
                {QA: (TEXT_A, None), QB: (TEXT_B, pl.Found(("запит",), (), None))},
                router=[with_deep_question(fa.answer_raw(), DQ)],
            ),
            "\n\n" + REPORT,
        ),
    }
    for i, (name, (path, llm, tail)) in enumerate(cases.items()):
        store = LocalStorage(tmp_path / str(i))
        ref = rq.topic(store)
        if path == "card":
            rq.put_routing(store, ref, [rq.d_choose(1, "alpha")])
        fac = partial(respond, knowledge=rq.knowledge(), llm=llm)
        got = list(reply(store, fac, rq.ALICE, ref, "Так, досліди.", rq.T0))
        assert isinstance(got[-1], Answered), (name, got[-1])
        shown = "".join(e.text for e in got if isinstance(e, Delta))
        recorded = open_topic(store, rq.ALICE, ref, rq.T0).sessions[-1].turns[-1].text
        assert recorded == normalize(shown), name
        assert shown.endswith(tail), name
        if path == "card":
            assert shown.startswith(REPLY), name


# ------------------------------------------------------------------ I2


def test_I2_deep_sources_are_the_union_of_the_searches_that_worked_each_url_once_in_sub_question_order() -> (
    None
):
    def slow_a(prompt: str) -> tuple[str, pl.Found | None]:
        time.sleep(0.3)  # the first sub-question finishes last when the searches run together
        return TEXT_A, found(PC)

    cases: list[tuple[list[str], dict[str, Any], tuple[Source, ...], str]] = [
        (
            [QA, QB, QC, QD],
            {QA: (TEXT_A, found(PA, PB)), QB: (TEXT_B, None), QC: DOWN, QD: (TEXT_D, found(PB, PC))},
            (SA, SB, SC),
            "\n\nДжерела: " + ", ".join([LINK_A, LINK_B, LINK_C]),
        ),
        (
            [QA, QB],
            {QA: (TEXT_A, pl.Found(("запит",), (), None)), QB: (TEXT_B, None)},
            (),
            "",
        ),
        (
            [QA, QB],
            {QA: slow_a, QB: (TEXT_B, found(PA, PC))},
            (SC, SA),
            "\n\nДжерела: " + ", ".join([LINK_C, LINK_A]),
        ),
        (
            [QA, QB, QC],
            {QA: DOWN, QB: (TEXT_B, found(PD)), QC: (TEXT_C, found(PD, PA))},
            (SD, SA),
            "\n\nДжерела: " + ", ".join([LINK_D, LINK_A]),
        ),
    ]
    for questions, searches, sources, line in cases:
        llm = deep_llm([plan_raw(questions=questions)], [report_raw()], searches)
        done = done_of(list(deep_research(DQ, ctx(), llm, REV)))
        assert done.event.sources == sources, questions
        assert done.text.endswith("\n\n" + REPORT + line), questions


# ------------------------------------------------------------------ I3


def test_I3_without_deep_question_no_plan_search_or_report_call_is_made() -> None:
    # the facilitator without the router
    llm = full_deep(streams=[Stream(list(DELTAS), card_answer(REPLY, "a_one"), FOUND_1)])
    items: list[Any] = list(respond(rq.context(routing=None), rq.knowledge(), llm))
    assert llm.deep_calls == []
    assert items[-1].reply == REPLY + LINE_1

    # the facilitator under the router: null, empty and blank deep_question
    for value in (None, "", "   ", "\n\t"):
        llm = full_deep(
            streams=[Stream(list(DELTAS), card_answer(REPLY, "a_one", deep_question=value), FOUND_1)]
        )
        items = list(respond(rq.context(), rq.knowledge(), llm))
        (stream,) = llm.of("stream")
        assert "deep_question" in stream.schema.model_fields, repr(value)
        assert llm.of("update") == [], repr(value)
        assert llm.deep_calls == [], repr(value)
        assert items[-1] == FacilitatorUpdate(
            reply=REPLY + LINE_1, current_phase_id="a_one", phase_exit_met=False, map_updates=[]
        ), repr(value)

    # the router's answer with null, empty and blank deep_question: the fact answer of S2
    for value in (None, "", "   "):
        llm = full_deep(
            router=[with_deep_question(fa.answer_raw(), value)],
            streams=[Stream(list(fa.DELTAS), fa.fact_raw(), fa.FOUND)],
        )
        items = list(converse(fa.context((), turn_no=1, history=[]), fa.knowledge(), llm, fa.no_lead))
        (stream,) = llm.of("stream")
        assert stream.schema is FactAnswer, repr(value)
        assert llm.deep_calls == [], repr(value)
        assert not any(isinstance(i, ResearchEvent) and i.depth == "deep" for i in items), repr(value)

    # with_deep itself: nothing changes
    first = FacilitatorUpdate(
        reply="Відповідь.", current_phase_id="a_one", phase_exit_met=False, map_updates=[]
    )
    for value in (None, "", "  "):
        llm = full_deep()
        given: list[Any] = [ReplyDelta("Відповідь."), first]
        assert list(with_deep(iter(given), partial(str_or_none, value), ctx(), llm, REV)) == given, repr(
            value
        )
        assert llm.deep_calls == [], repr(value)


# ------------------------------------------------------------------ I4


def test_I4_the_report_only_adds_fact_items_with_ids_unique_among_the_map_the_first_answer_and_each_other(
    tmp_path: Path,
) -> None:
    def items(*ids: str) -> list[MapItem]:
        return [MapItem(id=i, type="goal", text=f"пункт {i}", turn="t1") for i in ids]

    # ids of the form d<N>-<k> already in the map and among the first answer's changes; a repeated fact
    llm = deep_llm([plan_raw()], [report_raw(facts=["Факт А.", "Факт А.", "Факт Б."])])
    c = ctx(items("i1", "d3-1", "d3-3", "d3-6"), turn_no=3)
    done = done_of(list(deep_research(DQ, c, llm, REV, frozenset({"d3-2"}))))
    assert [u.model_dump() for u in done.map_updates] == [
        fact_update("d3-4", "Факт А.", "t3"),
        fact_update("d3-5", "Факт А.", "t3"),
        fact_update("d3-7", "Факт Б.", "t3"),
    ]

    # no facts: no changes
    llm = deep_llm([plan_raw()], [report_raw(facts=[])])
    assert done_of(list(deep_research(DQ, ctx(turn_no=5), llm, REV))).map_updates == ()

    # an id of another turn does not take this turn's number
    llm = deep_llm([plan_raw()], [report_raw(facts=[FACT_1])])
    done = done_of(list(deep_research(DQ, ctx(items("d2-1", "d5-2"), turn_no=5), llm, REV)))
    assert done.map_updates == (MapUpdate.model_validate(fact_update("d5-1", FACT_1, "t5")),)

    # through workspace: the first answer's own item is kept, two equal facts are two items in map.json
    store = LocalStorage(tmp_path)
    ref = rq.topic(store)
    rq.put_routing(store, ref, [rq.d_choose(1, "alpha")])
    own = fact_update("d1-1", "Своє: перші гроші за пів року.", "t1")
    llm = deep_llm(
        [plan_raw()],
        [report_raw(facts=[FACT_2, FACT_2])],
        streams=[Stream(list(DELTAS), card_answer(REPLY, "a_one", updates=[own], deep_question=DQ), None)],
    )
    got = list(
        reply(store, partial(respond, knowledge=rq.knowledge(), llm=llm), rq.ALICE, ref, "Так.", rq.T0)
    )
    assert isinstance(got[-1], Answered), got[-1]
    stored = rq.read_map(store, ref)["items"]
    assert {k: v for k, v in own.items() if k != "op"} in stored
    assert {"id": "d1-2", "type": "fact", "text": FACT_2, "turn": "t1"} in stored
    assert {"id": "d1-3", "type": "fact", "text": FACT_2, "turn": "t1"} in stored
    assert len(stored) == 3
