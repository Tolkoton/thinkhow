"""The deep cycle (S3), confirmed first (deep-research-confirm-first): the reply that decides on it only
shows the plan and asks; the person's next turn agrees (the shown sub-questions searched in parallel → one
report with sources), changes it (a new plan) or declines. Stores nothing: workspace keeps what waits.
"""

import contextvars
import re
from collections.abc import Callable, Iterator, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ValidationError

from thinkhow.facilitation.language import language_rule, listening_rule
from thinkhow.facilitation.settle import FIRST_REPLY_LINE, frame, sources_line
from thinkhow.facilitation.types import (
    DeepConsent,
    DeepPlan,
    DeepProposed,
    DeepReport,
    FacilitationContext,
    FacilitationError,
    FacilitatorUpdate,
    MapUpdate,
    PendingDeep,
    ReplyDelta,
    ResearchEvent,
    Source,
    clean_question,
)
from thinkhow.platform import llm as model

QUESTION_HEAD = "\n\n[Питання дослідження]\n"
SECTION = re.compile(r"^## (.+)$", re.M)


@dataclass(frozen=True)
class DeepDone:
    text: str
    map_updates: tuple[MapUpdate, ...]
    event: ResearchEvent


@dataclass(frozen=True)
class _Searched:
    question: str
    text: str
    found: model.Found | None


def _rules() -> dict[str, str]:
    """The rules of `deep.md`, by their `## ` headings."""
    text = (Path(__file__).with_name("deep.md")).read_text(encoding="utf-8")
    parts = SECTION.split(text)[1:]
    return {name.strip(): body.strip() for name, body in zip(parts[::2], parts[1::2], strict=True)}


RULES = _rules()


def propose(
    question: str, ctx: FacilitationContext, llm: model.Llm, rev: model.KnowledgeRev, first: bool
) -> PendingDeep:
    """Flow: one plan call (the first-reply line in its frame when `first`) → the proposal; no search."""
    state = f"{FIRST_REPLY_LINE}\n\n" if first else ""
    contents = _plan_contents(ctx, question, state)
    plan = _twice(lambda: llm.generate_json(_system("План", ctx), contents, DeepPlan, rev))
    return PendingDeep(question=question, intro=plan.intro, questions=list(plan.questions))


def proposal_text(pending: PendingDeep) -> str:
    """What the person sees: the sentence to them, the research question, a line per search."""
    return f"{pending.intro}\n\n{pending.question}\n{_steps(pending)}"


def run_deep(
    pending: PendingDeep,
    ctx: FacilitationContext,
    llm: model.Llm,
    rev: model.KnowledgeRev,
    taken: frozenset[str] = frozenset(),
) -> Iterator[ReplyDelta | DeepDone]:
    """Flow: the steps shown → the shown sub-questions searched in parallel → the report → the sources line
    → DeepDone. No plan: the searches are exactly the ones the person agreed to."""
    steps = _steps(pending)
    yield ReplyDelta(steps)
    found = _search_all(pending.questions, ctx, llm, rev)
    findings = [model.Turn("user", _findings(pending.question, found))]
    report = _twice(lambda: llm.generate_json(_system("Звіт", ctx), findings, DeepReport, rev))
    yield ReplyDelta("\n\n" + report.report)
    sources = _united_sources(found)
    line = sources_line(sources)
    if line:
        yield ReplyDelta(line)
    event = ResearchEvent(
        "deep", _united_queries(found), sources, _suggestions(found), pending.question, report.report
    )
    updates = _fact_items(report.facts, ctx, taken)
    yield DeepDone(steps + "\n\n" + report.report + line, updates, event)


def consent(
    ctx: FacilitationContext, llm: model.Llm, rev: model.KnowledgeRev
) -> Literal["yes", "change", "no", "other"]:
    """What the person's turn says to the proposal shown before it."""
    answer = _twice(lambda: llm.generate_json(_system("Згода", ctx), frame(ctx), DeepConsent, rev))
    return answer.answer


def with_deep(
    items: Iterator[ReplyDelta | FacilitatorUpdate | ResearchEvent],
    deep_question: Callable[[], str | None],
    ctx: FacilitationContext,
    llm: model.Llm,
    rev: model.KnowledgeRev,
) -> Iterator[ReplyDelta | FacilitatorUpdate | ResearchEvent | DeepProposed]:
    """Flow: pass the answer on; a deep question at its update (not after the person's «no») → the proposal
    after the answer, its event, the update grown."""
    for item in items:
        if not isinstance(item, FacilitatorUpdate):
            yield item
            continue
        question = None if ctx.deep_off else clean_question(deep_question())
        if question is None:
            yield item
            return
        yield from _grown(item, propose(question, ctx, llm, rev, first=False))
        return


def deep_offer(
    question: str, ctx: FacilitationContext, llm: model.Llm, rev: model.KnowledgeRev
) -> Iterator[ReplyDelta | FacilitatorUpdate | DeepProposed]:
    """The router's «answer» with a deep question: the proposal is the whole answer, an update that leads no
    card; on the topic's first reply the plan gets the first-reply line."""
    first = not any(t.role == "model" for t in ctx.history)
    yield from _proposed(propose(question, ctx, llm, rev, first), None)


def deep_agreed(
    pending: PendingDeep, ctx: FacilitationContext, llm: model.Llm, rev: model.KnowledgeRev
) -> Iterator[ReplyDelta | FacilitatorUpdate | ResearchEvent]:
    """«Yes» to the proposal: the research it showed, its event, an update that keeps the card's phase."""
    done: DeepDone | None = None
    for piece in run_deep(pending, ctx, llm, rev):
        if isinstance(piece, DeepDone):
            done = piece
        else:
            yield piece
    if done is None:
        return
    yield done.event
    yield FacilitatorUpdate(
        reply=done.text,
        current_phase_id=ctx.problem_map.phase_id,
        phase_exit_met=False,
        map_updates=list(done.map_updates),
    )


def deep_changed(
    pending: PendingDeep, ctx: FacilitationContext, llm: model.Llm, rev: model.KnowledgeRev
) -> Iterator[ReplyDelta | FacilitatorUpdate | DeepProposed]:
    """A change to the proposal: a new plan for the same question (the change is the person's turn)."""
    yield from _proposed(propose(pending.question, ctx, llm, rev, first=False), ctx.problem_map.phase_id)


def _proposed(
    pending: PendingDeep, phase: str | None
) -> Iterator[ReplyDelta | FacilitatorUpdate | DeepProposed]:
    text = proposal_text(pending)
    yield ReplyDelta(text)
    yield DeepProposed(pending)
    yield FacilitatorUpdate(reply=text, current_phase_id=phase, phase_exit_met=False, map_updates=[])


def _grown(
    update: FacilitatorUpdate, pending: PendingDeep
) -> Iterator[ReplyDelta | FacilitatorUpdate | DeepProposed]:
    """The proposal after an answer: one delta after a separator, its event, the update grown."""
    separator = "\n\n" if update.reply else ""
    text = separator + proposal_text(pending)
    yield ReplyDelta(text)
    yield DeepProposed(pending)
    yield update.model_copy(update={"reply": update.reply + text})


def _steps(pending: PendingDeep) -> str:
    return "\n".join(f"- {q}" for q in pending.questions)


def _system(rule: str, ctx: FacilitationContext) -> str:
    return f"{RULES[rule]}\n\n# Мова відповіді\n{language_rule(ctx.language)}\n{listening_rule(ctx.spoken)}"


def _plan_contents(ctx: FacilitationContext, question: str, state: str) -> list[model.Turn]:
    contents = frame(ctx, state)
    last = contents[-1]
    return [*contents[:-1], model.Turn("user", last.text + QUESTION_HEAD + question)]


def _search_all(
    questions: Sequence[str], ctx: FacilitationContext, llm: model.Llm, rev: model.KnowledgeRev
) -> list[_Searched]:
    """Every sub-question searched at once, each in the caller's context; the results in the plan's order."""
    system = _system("Пошук", ctx)
    with ThreadPoolExecutor(max_workers=len(questions)) as pool:
        futures = [
            pool.submit(contextvars.copy_context().run, _search_one, llm, system, q, rev) for q in questions
        ]
        results = [future.result() for future in futures]
    worked = [r for r in results if r is not None]
    if not worked:
        raise model.LlmUnavailable("every search of the deep cycle failed")
    return worked


def _search_one(llm: model.Llm, system: str, question: str, rev: model.KnowledgeRev) -> _Searched | None:
    """One sub-question searched; a search the model did not answer is left out (Q6)."""
    try:
        text, found = llm.search_text(system, question, rev)
    except model.LlmUnavailable:
        return None
    return _Searched(question, text, found)


def _findings(question: str, found: Sequence[_Searched]) -> str:
    parts = [f"## {s.question}\n{s.text}" for s in found]
    return f"[Питання людини]\n{question}\n\n[Знахідки]\n" + "\n\n".join(parts)


def _united_sources(found: Sequence[_Searched]) -> tuple[Source, ...]:
    unique: dict[str, Source] = {}
    for searched in found:
        for source in searched.found.sources if searched.found else ():
            unique.setdefault(source.url, Source(source.title, source.url))
    return tuple(unique.values())


def _united_queries(found: Sequence[_Searched]) -> tuple[str, ...]:
    unique: dict[str, None] = {}
    for searched in found:
        for query in searched.found.queries if searched.found else ():
            unique.setdefault(query, None)
    return tuple(unique)


def _suggestions(found: Sequence[_Searched]) -> str | None:
    html = [s.found.suggestions_html for s in found if s.found and s.found.suggestions_html]
    return html[-1] if html else None


def _fact_items(
    facts: Sequence[str], ctx: FacilitationContext, taken: frozenset[str]
) -> tuple[MapUpdate, ...]:
    """Each fact of the report its own item, with an id that is in neither the map nor the answer's (I4)."""
    used = {item.id for item in ctx.problem_map.items} | set(taken)
    items: list[MapUpdate] = []
    k = 0
    for fact in facts:
        k += 1
        while f"d{ctx.turn_no}-{k}" in used:
            k += 1
        fid = f"d{ctx.turn_no}-{k}"
        used.add(fid)
        items.append(MapUpdate(op="add", id=fid, type="fact", text=fact, turn=f"t{ctx.turn_no}"))
    return tuple(items)


def _twice[M: BaseModel](call: Callable[[], M]) -> M:
    """One retry of an invalid answer; invalid twice → FacilitationError."""
    for attempt in (1, 2):
        try:
            return call()
        except ValidationError as exc:
            if attempt == 2:
                raise FacilitationError("the deep cycle's answer stayed invalid after one retry") from exc
    raise AssertionError("unreachable")
