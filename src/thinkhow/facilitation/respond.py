"""One reply of the facilitator: one Gemini call by a card, `reply` streamed, one valid update (F4).

The rules are PoC 101's instruction (`rules.md`, two lines changed: skel-facilitation Q5).
"""

from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, create_model

from thinkhow.facilitation.converse import converse
from thinkhow.facilitation.deep import with_deep
from thinkhow.facilitation.language import NO_LANGUAGE_RULE as NO_LANGUAGE_RULE
from thinkhow.facilitation.language import language_rule as language_rule
from thinkhow.facilitation.language import listening_rule
from thinkhow.facilitation.settle import RESEARCH_SECTION as RESEARCH_SECTION
from thinkhow.facilitation.settle import frame, settle, with_research
from thinkhow.facilitation.settle import sources_line as sources_line
from thinkhow.facilitation.types import (
    FacilitationContext,
    FacilitatorUpdate,
    MapUpdate,
    ReplyDelta,
    ResearchEvent,
    RoutingEvent,
    clean_question,
)
from thinkhow.knowledge import Card, CurrentKnowledge, MemoryRecord, card_prompt
from thinkhow.platform import llm as model

RULES = (Path(__file__).with_name("rules.md")).read_text(encoding="utf-8").rstrip("\n")
RETRY_ASK = "Поверни лише оновлення до своєї відповіді вище: фаза, вихід, зміни карти."
ROUTED_SECTION = (Path(__file__).with_name("routed.md")).read_text(encoding="utf-8").rstrip("\n")
DEEP_FIELD = (Path(__file__).with_name("deep_field.md")).read_text(encoding="utf-8").rstrip("\n")
FREE_MODE_LINE = "[Стан] Вільний режим уже триває: людина чула, що картка не підходить. Не кажи цього знову."
JUST_CHOSEN_LINE = "[Стан] Метод щойно обрано: почни з його пояснення за правилом вище, далі — перше питання."
FIRST_REPLY_LINE = "[Стан] Перша відповідь у темі: скажи про це за правилом вище."


def respond(
    ctx: FacilitationContext, knowledge: CurrentKnowledge, llm: model.Llm
) -> Iterator[ReplyDelta | FacilitatorUpdate | RoutingEvent | ResearchEvent]:
    """The app's Facilitate: without routing — leading by the card, as before; with it — converse.
    The Knowledge is taken once for the whole reply (`now()`: one revision per reply, learning-loop S4)."""
    knowledge = knowledge.now()
    if ctx.routing is None:
        return lead(ctx, knowledge, llm)
    return converse(ctx, knowledge, llm, lead)


def lead(
    ctx: FacilitationContext, knowledge: CurrentKnowledge, llm: model.Llm
) -> Iterator[ReplyDelta | FacilitatorUpdate | ResearchEvent]:
    """Flow: the card → one streamed call → pass the deltas on → settle the update → what search found."""
    card = knowledge.cards.get(ctx.card_id)
    if card is None:
        raise ValueError(f"no card {ctx.card_id!r} in the Knowledge")
    system = system_instruction(card, knowledge.memory, ctx.language, ctx.routing is not None, ctx.spoken)
    contents, rev = _contents(ctx), knowledge.rev_pair()
    shown: list[str] = []
    raw, found = "", None
    stream_schema = _routed(card)[0] if ctx.routing is not None else answer_schema(card)
    for event in llm.stream_json(system, contents, stream_schema, rev):
        if isinstance(event, model.ReplyDelta):
            shown.append(event.text)
            yield ReplyDelta(event.text)
        else:
            raw, found = event.raw_json, event.found
    routed, asked = ctx.routing is not None, _Asked()
    schemas = _routed(card) if routed else (answer_schema(card), update_schema(card))
    fill = asked.take if routed else _same
    settled = settle(llm, system, contents, rev, "".join(shown), raw, *schemas, RETRY_ASK, fill)
    yield from with_deep(with_research(settled, found), asked.get, ctx, llm, rev)


def system_instruction(
    card: Card,
    memory: Sequence[MemoryRecord],
    language: str | None = None,
    routed: bool = False,
    spoken: bool = False,
) -> str:
    """The rules, the person's language (F13), whether they listen (task 308), under the router its section,
    then the card and its `facilitator` notes (learning-loop S4)."""
    head = f"{RULES}\n\n# Мова відповіді\n{language_rule(language)}\n{listening_rule(spoken)}"
    if routed:
        head += f"\n{ROUTED_SECTION}\n\n{RESEARCH_SECTION}\n\n{DEEP_FIELD}\n"
    mine = [r for r in memory if r.audience == "facilitator" and card.id in r.cards]
    return f"{head}\n# Картка\n{card_prompt(card)}\n# Пам'ять досвіду\n{_memory_text(mine)}\n"


def answer_schema(card: Card) -> type[FacilitatorUpdate]:
    """FacilitatorUpdate with current_phase_id narrowed to a card phase or null; `reply` stays first."""
    return create_model(
        "FacilitatorAnswer", __base__=FacilitatorUpdate, current_phase_id=(_phases(card), ...)
    )


def update_schema(card: Card) -> type[BaseModel]:
    """The update without `reply`: what the update-only retry asks for (Q2)."""
    return create_model(
        "FacilitatorUpdateOnly",
        current_phase_id=(_phases(card), ...),
        phase_exit_met=(bool, ...),
        map_updates=(list[MapUpdate], ...),
    )


def _phases(card: Card) -> Any:
    """A phase of the card, or None: the card does not fit (free mode, facilitator-free-mode Q1)."""
    return Literal[tuple(phase.id for phase in card.facilitator.phases)] | None


class _Asked:
    """The deep question the update carried: taken off its fields by `fill`, read when the update comes."""

    def __init__(self) -> None:
        self.question: str | None = None

    def take(self, fields: dict[str, Any]) -> dict[str, Any]:
        self.question = clean_question(fields.pop("deep_question", None))
        return fields

    def get(self) -> str | None:
        return self.question


def _routed(card: Card) -> tuple[type[BaseModel], type[BaseModel]]:
    """Under the router the card's schemas get `deep_question` last (research-deep Q1)."""
    deep: Any = (str | None, None)
    full = create_model("RoutedFacilitatorAnswer", __base__=answer_schema(card), deep_question=deep)
    update = create_model("RoutedFacilitatorUpdateOnly", __base__=update_schema(card), deep_question=deep)
    return full, update


def _same(fields: dict[str, Any]) -> dict[str, Any]:
    return fields


def _contents(ctx: FacilitationContext) -> list[model.Turn]:
    return frame(ctx, _state(ctx))


def _state(ctx: FacilitationContext) -> str:
    """A state line in the frame: the card chosen on this very turn (task 205), on the topic's first reply
    with the first-reply line (task 310); or free mode under way (I4).

    Free mode only without the router: under it a card that does not fit goes back to the router.
    """
    routing = ctx.routing or ()
    if routing and routing[-1].kind == "choose" and routing[-1].turn == ctx.turn_no:
        first = ctx.routing is not None and not any(t.role == "model" for t in ctx.history)
        return f"{JUST_CHOSEN_LINE}\n{FIRST_REPLY_LINE}\n\n" if first else f"{JUST_CHOSEN_LINE}\n\n"
    problem_map = ctx.problem_map
    if ctx.routing is None and problem_map.phase_id is None and problem_map.last_turn > 0:
        return f"{FREE_MODE_LINE}\n\n"
    return ""


def _memory_text(memory: Sequence[MemoryRecord]) -> str:
    if not memory:
        return "(поки порожня)"
    return "\n\n".join(
        f"### {r.id} — {r.title}\nКартки: {', '.join(r.cards)}.\nЩо помітили: {r.noticed}\n"
        f"Що робити: {r.do}\nПідстава: {r.basis}"
        for r in memory
    )
