"""A direct question of fact answered at once (the router's «answer», N1 v5): one streamed call with search.

No card, no facilitator rules: a short answer by `answer.md`, the sources line, one question, a `fact`.
"""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

from thinkhow.facilitation.language import language_rule, listening_rule
from thinkhow.facilitation.settle import RESEARCH_SECTION, frame, settle, with_research
from thinkhow.facilitation.types import (
    FacilitationContext,
    FacilitatorUpdate,
    FactAnswer,
    FactUpdate,
    ReplyDelta,
    ResearchEvent,
)
from thinkhow.knowledge import CurrentKnowledge
from thinkhow.platform import llm as model

ANSWER_RULES = (Path(__file__).with_name("answer.md")).read_text(encoding="utf-8").rstrip("\n")
FACT_RETRY_ASK = "Поверни лише зміни карти до своєї відповіді вище."


def answer_fact(
    ctx: FacilitationContext, knowledge: CurrentKnowledge, llm: model.Llm
) -> Iterator[ReplyDelta | FacilitatorUpdate | ResearchEvent]:
    """Flow: the instruction → one streamed call → the deltas on → settle the update → what search found."""
    system, contents, rev = answer_instruction(ctx.language, ctx.spoken), frame(ctx), knowledge.rev_pair()
    shown: list[str] = []
    raw, found = "", None
    for event in llm.stream_json(system, contents, FactAnswer, rev):
        if isinstance(event, model.ReplyDelta):
            shown.append(event.text)
            yield ReplyDelta(event.text)
        else:
            raw, found = event.raw_json, event.found
    settled = settle(
        llm, system, contents, rev, "".join(shown), raw, FactAnswer, FactUpdate, FACT_RETRY_ASK, _no_card
    )
    yield from with_research(settled, found)


def answer_instruction(language: str | None, spoken: bool = False) -> str:
    """`answer.md`, the person's language, whether they listen, then the facts-about-the-world rule."""
    head = f"{ANSWER_RULES}\n\n# Мова відповіді\n{language_rule(language)}\n{listening_rule(spoken)}"
    return f"{head}\n{RESEARCH_SECTION}\n"


def _no_card(fields: dict[str, Any]) -> dict[str, Any]:
    """A fact answer leads no card: no phase, no exit."""
    return fields | {"current_phase_id": None, "phase_exit_met": False}
