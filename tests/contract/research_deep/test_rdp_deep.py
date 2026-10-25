"""Contract tests of research-deep, `facilitation/deep.py`: the plan schema, `deep_research` (its deltas, its
`DeepDone`, its calls, its rules, its errors), `with_deep`, and the parallel searches with their failures
(Seam 3) (slice tester; from the contract)."""

import threading
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from rdp_fakes import (
    DQ,
    FACT_1,
    FACT_2,
    INVALID_PLAN,
    INVALID_REPORT,
    LINE_ABC,
    LINK_A,
    LINK_C,
    PLAN_RULE,
    QA,
    QB,
    QC,
    QUERIES_ABC,
    QUESTION_HEAD,
    REPORT,
    REPORT_RULE,
    SA,
    SB,
    SC,
    SEARCH_RULE,
    SEARCHES_ABC,
    TEXT_A,
    TEXT_B,
    TEXT_C,
    ctx,
    deep_llm,
    fact_update,
    flat,
    full_deep,
    plan_raw,
    report_raw,
    rq,
    steps_lines,
    want_steps,
)

from thinkhow.facilitation import FacilitationError
from thinkhow.facilitation.deep import DeepDone, deep_research, with_deep
from thinkhow.facilitation.settle import frame
from thinkhow.facilitation.types import (
    DeepPlan,
    DeepReport,
    FacilitatorUpdate,
    MapUpdate,
    ReplyDelta,
    ResearchEvent,
    Source,
)
from thinkhow.platform import llm as pl
from thinkhow.platform import log

REV = pl.KnowledgeRev(rev=3, n=7)
PL = "Polski (pl-PL)"  # the person's language, named in each rule of the cycle (question Q1 of the hand-in)
DEEP_MD = Path(__file__).resolve().parents[3] / "src" / "thinkhow" / "facilitation" / "deep.md"


def run(llm: Any, question: str = DQ, c: Any = None, taken: frozenset[str] = frozenset()) -> list[Any]:
    return list(deep_research(question, c if c is not None else ctx(), llm, REV, taken))


def done_of(items: list[Any]) -> DeepDone:
    assert isinstance(items[-1], DeepDone), items[-1]
    return items[-1]


def deep_event(
    queries: tuple[str, ...] = QUERIES_ABC,
    sources: tuple[Source, ...] = (SA, SB, SC),
    html: str | None = "<div>підказки Б</div>",
    question: str = DQ,
    report: str = REPORT,
) -> ResearchEvent:
    return ResearchEvent(
        depth="deep",
        queries=queries,
        sources=sources,
        suggestions_html=html,
        question=question,
        report=report,
    )


# ------------------------------------------------------------------ the plan schema


def test_deep_plan_has_a_non_empty_intro_and_2_to_4_non_empty_sub_questions() -> None:
    for n in (2, 3, 4):
        plan = DeepPlan.model_validate_json(plan_raw(questions=[f"Підпитання {i}?" for i in range(n)]))
        assert len(plan.questions) == n
    for questions in ([], ["Одне?"], [f"П {i}?" for i in range(5)], ["Перше?", ""]):
        with pytest.raises(ValidationError):
            DeepPlan.model_validate_json(plan_raw(questions=questions))
    with pytest.raises(ValidationError):
        DeepPlan.model_validate_json(plan_raw(intro=""))


# ------------------------------------------------------------------ deep_research


def test_deep_research_streams_the_steps_then_the_report_then_the_sources_line_then_deep_done() -> None:
    items = run(full_deep())
    assert [type(i).__name__ for i in items] == ["ReplyDelta", "ReplyDelta", "ReplyDelta", "DeepDone"]
    steps, report, line = (i.text for i in items[:3])
    assert steps_lines(steps) == want_steps()
    assert report == "\n\n" + REPORT
    assert line == LINE_ABC
    done = done_of(items)
    assert done.text == steps + "\n\n" + REPORT + LINE_ABC
    assert done.event == deep_event()
    assert done.map_updates == (
        MapUpdate.model_validate(fact_update("d3-1", FACT_1, "t3")),
        MapUpdate.model_validate(fact_update("d3-2", FACT_2, "t3")),
    )


def test_deep_research_without_any_source_has_no_sources_line_in_the_stream_or_the_text() -> None:
    empty = pl.Found(("Berater Auswahl",), (), None)
    llm = deep_llm([plan_raw(questions=[QA, QB])], [report_raw()], {QA: (TEXT_A, empty), QB: (TEXT_B, None)})
    items = run(llm)
    texts = [i.text for i in items if isinstance(i, ReplyDelta)]
    assert all("Джерела:" not in t for t in texts)
    done = done_of(items)
    assert "Джерела:" not in done.text
    assert done.text == "".join(texts)
    assert done.text.endswith("\n\n" + REPORT)
    assert done.event.sources == ()


def test_deep_research_plans_from_the_frame_and_the_question_searches_each_sub_question_then_reports() -> (
    None
):
    llm = full_deep()
    c = ctx()
    run(llm, c=c)
    (plan,) = llm.of("plan")
    want = frame(c)
    assert plan.contents[:-1] == want[:-1]
    assert plan.contents[-1].role == "user"
    assert plan.contents[-1].text == want[-1].text + QUESTION_HEAD + DQ
    assert plan.rev == REV
    assert issubclass(plan.schema, DeepPlan)
    searches = llm.of("search")
    assert sorted(s.prompt or "" for s in searches) == sorted([QA, QB, QC])
    assert all(s.rev == REV for s in searches)
    (report,) = llm.of("report")
    assert report.rev == REV
    assert issubclass(report.schema, DeepReport)
    assert len(report.contents) == 1 and report.contents[0].role == "user"
    body = report.contents[0].text
    assert DQ in body and TEXT_A in body and TEXT_B in body and TEXT_C in body
    assert [c.kind for c in llm.calls if c.kind in ("stream", "update", "router")] == []
    assert [c.kind for c in llm.calls].index("plan") == 0
    assert [c.kind for c in llm.calls][-1] == "report"


def test_deep_md_rules_go_to_their_calls_each_with_the_language_of_the_person() -> None:
    text = DEEP_MD.read_text(encoding="utf-8")
    lines = text.split("\n")
    assert lines.index("## План") < lines.index("## Пошук") < lines.index("## Звіт")
    assert (
        flat(PLAN_RULE) in flat(text) and flat(SEARCH_RULE) in flat(text) and flat(REPORT_RULE) in flat(text)
    )

    llm = full_deep()
    run(llm, c=ctx(language="Polski (pl-PL)"))
    (plan,) = llm.of("plan")
    (report,) = llm.of("report")
    searches = llm.of("search")
    assert len(searches) == 3
    assert flat(PLAN_RULE) in flat(plan.system) and PL in plan.system
    assert flat(SEARCH_RULE) not in flat(plan.system) and flat(REPORT_RULE) not in flat(plan.system)
    for s in searches:
        assert flat(SEARCH_RULE) in flat(s.system) and PL in s.system
        assert flat(PLAN_RULE) not in flat(s.system) and flat(REPORT_RULE) not in flat(s.system)
    assert flat(REPORT_RULE) in flat(report.system) and PL in report.system
    assert flat(PLAN_RULE) not in flat(report.system) and flat(SEARCH_RULE) not in flat(report.system)


def test_an_invalid_plan_gets_one_retry_and_twice_is_a_facilitation_error_before_any_search() -> None:
    llm = deep_llm([INVALID_PLAN, plan_raw()], [report_raw()])
    assert done_of(run(llm)).event == deep_event()
    assert len(llm.of("plan")) == 2

    twice = deep_llm([INVALID_PLAN, plan_raw(questions=[QA])], [report_raw()])
    with pytest.raises(FacilitationError):
        run(twice)
    assert len(twice.of("plan")) == 2
    assert twice.of("search") == [] and twice.of("report") == []


def test_an_invalid_report_gets_one_retry_and_twice_is_a_facilitation_error() -> None:
    llm = deep_llm([plan_raw()], [INVALID_REPORT, report_raw()])
    assert done_of(run(llm)).event == deep_event()
    assert len(llm.of("report")) == 2

    twice = deep_llm([plan_raw()], [INVALID_REPORT, json_report_without_text()])
    with pytest.raises(FacilitationError):
        run(twice)
    assert len(twice.of("report")) == 2


def json_report_without_text() -> str:
    return report_raw(report="")


# ------------------------------------------------------------------ with_deep


def test_with_deep_reads_deep_question_when_the_update_came_and_appends_the_cycle_to_the_held_update() -> (
    None
):
    quick = ResearchEvent(depth="quick", queries=("Mittelstand",), sources=(SA,), suggestions_html=None)
    first = FacilitatorUpdate(
        reply="Звучить як ринок. Починаю.",
        current_phase_id="a_two",
        phase_exit_met=True,
        map_updates=[MapUpdate.model_validate(fact_update("d3-1", "Мета: перші гроші.", "t3"))],
    )
    asked: dict[str, str | None] = {"q": None}

    def items() -> Any:
        yield ReplyDelta("Звучить як ринок. ")
        yield ReplyDelta("Починаю.")
        yield quick
        asked["q"] = DQ  # what `fill` took off during `settle`, known only when the update arrives
        yield first

    llm = full_deep()
    got: list[Any] = list(with_deep(items(), lambda: asked["q"], ctx(), llm, REV))
    assert got[:3] == [ReplyDelta("Звучить як ринок. "), ReplyDelta("Починаю."), quick]
    assert [type(i).__name__ for i in got[3:]] == [
        "ReplyDelta",
        "ReplyDelta",
        "ReplyDelta",
        "ResearchEvent",
        "FacilitatorUpdate",
    ]
    steps = got[3].text
    assert steps.startswith("\n\n")
    assert steps_lines(steps[2:]) == want_steps()
    assert got[4] == ReplyDelta("\n\n" + REPORT)
    assert got[5] == ReplyDelta(LINE_ABC)
    assert got[6] == deep_event()
    update = got[7]
    assert update.reply == "Звучить як ринок. Починаю." + "\n\n" + steps[2:] + "\n\n" + REPORT + LINE_ABC
    assert update.reply == "".join(i.text for i in got if isinstance(i, ReplyDelta))
    assert (update.current_phase_id, update.phase_exit_met) == ("a_two", True)
    assert [u.model_dump() for u in update.map_updates] == [
        fact_update("d3-1", "Мета: перші гроші.", "t3"),
        fact_update("d3-2", FACT_1, "t3"),
        fact_update("d3-3", FACT_2, "t3"),
    ]


# ------------------------------------------------------------------ Seam 3: parallel searches, failures


def test_seam3_searches_run_in_parallel_and_their_results_keep_the_order_of_the_sub_questions() -> None:
    barrier = threading.Barrier(3, timeout=5.0)
    others_done = threading.Event()
    lock = threading.Lock()
    finished: list[str] = []
    results = dict(SEARCHES_ABC)

    def search(prompt: str) -> tuple[str, pl.Found | None]:
        barrier.wait()  # a sequential implementation breaks here: the test is red
        if prompt == QA:
            assert others_done.wait(timeout=5.0), "the other searches did not finish while the first waited"
        with lock:
            finished.append(prompt)
            if len([p for p in finished if p != QA]) == 2:
                others_done.set()
        answer: tuple[str, pl.Found | None] = results[prompt]
        return answer

    llm = deep_llm([plan_raw()], [report_raw()], {QA: search, QB: search, QC: search})
    done = done_of(run(llm))
    assert finished[-1] == QA, finished
    assert done.event.sources == (SA, SB, SC)
    assert done.event.queries == QUERIES_ABC
    body = llm.of("report")[0].contents[0].text
    assert body.index(TEXT_A) < body.index(TEXT_B) < body.index(TEXT_C)
    assert done.text.endswith(LINE_ABC)


def test_seam3_a_failed_search_is_left_out_and_the_report_is_made_of_the_rest() -> None:
    barrier = threading.Barrier(3, timeout=5.0)

    def search(prompt: str) -> tuple[str, pl.Found | None]:
        barrier.wait()  # the failing one reaches the barrier first, so the rest do not wait for the limit
        if prompt == QB:
            raise pl.LlmUnavailable("search down")
        answer: tuple[str, pl.Found | None] = SEARCHES_ABC[prompt]
        return answer

    llm = deep_llm([plan_raw()], [report_raw()], {QA: search, QB: search, QC: search})
    done = done_of(run(llm))
    body = llm.of("report")[0].contents[0].text
    assert TEXT_A in body and TEXT_C in body
    assert TEXT_B not in body
    assert done.event.sources == (SA, SC)
    assert done.event.queries == ("Mittelstand Berater Auswahl", "Berater erste Kunden Sachsen")
    assert done.text.endswith("\n\n" + REPORT + "\n\nДжерела: " + LINK_A + ", " + LINK_C)


def test_seam3_every_llm_call_line_of_the_searches_carries_the_request_id(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    logs = rq.install_log_capture(monkeypatch, capsys)
    answers = {QA: TEXT_A, QB: TEXT_B, QC: TEXT_C}

    class Models:
        def generate_content(self, *args: Any, **kwargs: Any) -> Any:
            contents = str(args) + str(kwargs.get("contents"))
            (prompt,) = [q for q in answers if q in contents]
            gm = rq.meta([f"запит {prompt}"], [rq.web(f"https://x.example/{len(prompt)}", "Джерело")])
            return rq.response(answers[prompt], gm, rq.GENAI_USAGE)

    class Client:
        models = Models()

    vertex = pl.VertexLlm(
        Client(), "gemini-4-argon", 300.0, 3, sleep=rq.Sleeps(), clock=lambda: 10.0, search=True
    )
    scripted = full_deep()

    class Mixed:
        """Plan and report by the fake; every search through VertexLlm, which writes the `llm_call` lines."""

        def stream_json(self, *args: Any, **kwargs: Any) -> Any:
            raise AssertionError("no streamed call in the deep cycle")

        def generate_json(self, *args: Any, **kwargs: Any) -> Any:
            return scripted.generate_json(*args, **kwargs)

        def search_text(self, system: str, prompt: str, rev: Any) -> Any:
            return vertex.search_text(system, prompt, rev)

    token = log.request_id.set("rid-deep-7")
    try:
        done = done_of(run(Mixed()))
    finally:
        log.request_id.reset(token)
    assert done.event.depth == "deep"
    lines = [line for line in logs.events("llm_call") if line.get("search") is True]
    assert len(lines) == 3
    assert [line.get("request_id") for line in lines] == ["rid-deep-7"] * 3


def test_seam3_all_searches_failed_is_llm_unavailable_without_a_report() -> None:
    down = pl.LlmUnavailable("search down")
    llm = deep_llm([plan_raw()], [report_raw()], {QA: down, QB: down, QC: down})
    with pytest.raises(pl.LlmUnavailable):
        run(llm)
    assert llm.of("report") == []
