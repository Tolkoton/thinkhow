"""What every streamed answer of facilitation shares: settling its update, the sources line, the research.

Used by `respond` (the card's facilitator) and `answer` (a fact answered at once). Imports neither of them:
the dependencies run one way, `converse` → `answer` → `settle` and `respond` → `settle` (fact-answer Q7).
"""

from collections.abc import Callable, Iterator, Sequence
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from thinkhow.facilitation.types import (
    FacilitationContext,
    FacilitationError,
    FacilitatorUpdate,
    ReplyDelta,
    ResearchEvent,
    Source,
)
from thinkhow.platform import llm as model

RESEARCH_SECTION = (Path(__file__).with_name("research.md")).read_text(encoding="utf-8").rstrip("\n")
SOURCES_HEAD = "\n\nДжерела: "
Fill = Callable[[dict[str, Any]], dict[str, Any]]


def settle(
    llm: model.Llm,
    system: str,
    contents: list[model.Turn],
    rev: model.KnowledgeRev,
    shown: str,
    raw: str,
    full: type[BaseModel],
    update_only: type[BaseModel],
    retry_ask: str,
    fill: Fill,
) -> Iterator[ReplyDelta | FacilitatorUpdate]:
    """Flow: valid streamed JSON → the update; invalid after shown text → update-only retry; else full."""
    parsed = _parse(full, raw)
    if parsed is not None:
        reply = str(parsed.model_dump()["reply"])
        if not shown:
            yield ReplyDelta(reply)
        yield _plain(fill(parsed.model_dump() | {"reply": shown or reply}))
        return
    if shown:
        retry = [*contents, model.Turn("model", shown), model.Turn("user", retry_ask)]
        update = _retry(lambda: llm.generate_json(system, retry, update_only, rev))
        yield _plain(fill(update.model_dump() | {"reply": shown}))
        return
    answer = _retry(lambda: llm.generate_json(system, contents, full, rev))
    yield ReplyDelta(str(answer.model_dump()["reply"]))
    yield _plain(fill(answer.model_dump()))


def with_research(
    items: Iterator[ReplyDelta | FacilitatorUpdate], found: model.Found | None
) -> Iterator[ReplyDelta | FacilitatorUpdate | ResearchEvent]:
    """Flow: pass the answer on; before its update — the sources line and the research event (S1, I1)."""
    if found is None or not (found.queries or found.sources):
        yield from items
        return
    for item in items:
        if isinstance(item, FacilitatorUpdate):
            event = _research(found)
            line = sources_line(event.sources)
            if line:
                yield ReplyDelta(line)
            yield event
            yield item.model_copy(update={"reply": item.reply + line})
            return
        yield item


def sources_line(sources: Sequence[Source]) -> str:
    """The line of sources under an answer, the same in the stream and in `reply`; none without sources."""
    if not sources:
        return ""
    links = (f"[{_title(s.title)}]({_url(s.url)})" for s in sources)
    return SOURCES_HEAD + ", ".join(links)


def frame(ctx: FacilitationContext, state: str = "") -> list[model.Turn]:
    """The topic's history, then one frame: the map now, a state line if any, the person's turn."""
    last = (
        f"[Карта проблеми зараз]\n{ctx.problem_map.model_dump_json()}\n\n{state}"
        f"[Репліка людини #{ctx.turn_no}]\n{ctx.text}"
    )
    return [*(model.Turn(t.role, t.text) for t in ctx.history), model.Turn("user", last)]


def _research(found: model.Found) -> ResearchEvent:
    sources = tuple(Source(s.title, s.url) for s in found.sources)
    return ResearchEvent("quick", found.queries, sources, found.suggestions_html)


def _title(title: str) -> str:
    return title.replace("[", "").replace("]", "")


def _url(url: str) -> str:
    return url.replace("(", "%28").replace(")", "%29")


def _parse(schema: type[BaseModel], raw: str) -> BaseModel | None:
    try:
        return schema.model_validate_json(raw)
    except ValidationError:
        return None


def _retry[M: BaseModel](call: Callable[[], M]) -> M:
    try:
        result: M = call()
    except ValidationError as exc:
        raise FacilitationError("the model's update stayed invalid after one retry") from exc
    return result


def _plain(fields: dict[str, Any]) -> FacilitatorUpdate:
    """Exactly FacilitatorUpdate, not the narrowed schema subclass."""
    return FacilitatorUpdate.model_validate(fields)
