"""One reply of the facilitator: one Gemini call by a card, `reply` streamed, one valid update (F4).

The rules are PoC 101's instruction (`rules.md`, two lines changed: skel-facilitation Q5).
"""

from collections.abc import Callable, Iterator, Sequence
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ValidationError, create_model

from thinkhow.facilitation.types import (
    FacilitationContext,
    FacilitationError,
    FacilitatorUpdate,
    MapUpdate,
    ProblemMap,
    ReplyDelta,
)
from thinkhow.knowledge import Card, CurrentKnowledge, MemoryRecord, card_prompt
from thinkhow.platform import llm as model

RULES = (Path(__file__).with_name("rules.md")).read_text(encoding="utf-8").rstrip("\n")
NO_LANGUAGE_RULE = "Ніколи не відповідай російською: на репліку російською відповідай українською."
RETRY_ASK = "Поверни лише оновлення до своєї відповіді вище: фаза, вихід, зміни карти."
FREE_MODE_LINE = "[Стан] Вільний режим уже триває: людина чула, що картка не підходить. Не кажи цього знову."


def respond(
    ctx: FacilitationContext, knowledge: CurrentKnowledge, llm: model.Llm
) -> Iterator[ReplyDelta | FacilitatorUpdate]:
    """Flow: the card → one streamed call → pass the deltas on → settle the update (retry it at most once)."""
    card = knowledge.cards.get(ctx.card_id)
    if card is None:
        raise ValueError(f"no card {ctx.card_id!r} in the Knowledge")
    system = system_instruction(card, knowledge.memory, ctx.language)
    contents, rev = _contents(ctx), knowledge.rev_pair()
    shown: list[str] = []
    raw = ""
    for event in llm.stream_json(system, contents, answer_schema(card), rev):
        if isinstance(event, model.ReplyDelta):
            shown.append(event.text)
            yield ReplyDelta(event.text)
        else:
            raw = event.raw_json
    yield from _settle(card, llm, system, contents, rev, "".join(shown), raw)


def system_instruction(card: Card, memory: Sequence[MemoryRecord], language: str | None = None) -> str:
    """The rules as they are, then the person's language (F13), the card and the memory."""
    head = f"{RULES}\n\n# Мова відповіді\n{language_rule(language)}\n"
    return f"{head}\n# Картка\n{card_prompt(card)}\n# Пам'ять досвіду\n{_memory_text(memory)}\n"


def language_rule(language: str | None) -> str:
    """The person's language first, Russian never; with no language chosen, only the ban (F13, AC3)."""
    if language is None:
        return NO_LANGUAGE_RULE
    return (
        f"Відповідай мовою людини — {language}: цю мову вона обрала для розмов з ThinkHow, "
        "і це правило важливіше за «мовою останньої репліки» вище. "
        "Іншою мовою — лише якщо людина прямо попросить. "
        "Ніколи не відповідай російською — ні на репліку російською, ні на прохання."
    )


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


def _settle(
    card: Card,
    llm: model.Llm,
    system: str,
    contents: list[model.Turn],
    rev: model.KnowledgeRev,
    shown: str,
    raw: str,
) -> Iterator[ReplyDelta | FacilitatorUpdate]:
    parsed = _parse(answer_schema(card), raw)
    if parsed is not None:
        if not shown:
            yield ReplyDelta(parsed.reply)
        yield _plain(parsed.model_dump() | {"reply": shown or parsed.reply})
        return
    if shown:
        retry = [*contents, model.Turn("model", shown), model.Turn("user", RETRY_ASK)]
        update = _retry(lambda: llm.generate_json(system, retry, update_schema(card), rev))
        yield _plain(update.model_dump() | {"reply": shown})
        return
    full = _retry(lambda: llm.generate_json(system, contents, answer_schema(card), rev))
    yield ReplyDelta(full.reply)
    yield _plain(full.model_dump())


def _parse(schema: type[FacilitatorUpdate], raw: str) -> FacilitatorUpdate | None:
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


def _phases(card: Card) -> Any:
    """A phase of the card, or None: the card does not fit (free mode, facilitator-free-mode Q1)."""
    return Literal[tuple(phase.id for phase in card.facilitator.phases)] | None


def _contents(ctx: FacilitationContext) -> list[model.Turn]:
    frame = (
        f"[Карта проблеми зараз]\n{ctx.problem_map.model_dump_json()}\n\n{_state(ctx.problem_map)}"
        f"[Репліка людини #{ctx.turn_no}]\n{ctx.text}"
    )
    return [*(model.Turn(t.role, t.text) for t in ctx.history), model.Turn("user", frame)]


def _state(problem_map: ProblemMap) -> str:
    """Free mode already under way — the person heard it once — is said to the model in the frame (I4)."""
    if problem_map.phase_id is None and problem_map.last_turn > 0:
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
