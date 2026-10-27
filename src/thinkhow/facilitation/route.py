"""The router: one model call from the cards' router halves to a decision — offer, ask or choose (F5).

Reads only `card.router` and `card.title` (S1 → S2). Does NOT stream, store or read the experience memory.
"""

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import ValidationError, create_model, field_validator, model_validator

from thinkhow.facilitation.language import language_rule, listening_rule
from thinkhow.facilitation.types import (
    Candidate,
    Decision,
    FacilitationContext,
    FacilitationError,
    Profile,
    _Frozen,
    clean_question,
)
from thinkhow.knowledge import Card, CurrentKnowledge
from thinkhow.platform import llm as model

ROUTER_RULES = (Path(__file__).with_name("router.md")).read_text(encoding="utf-8").rstrip("\n")
CARDS_HEAD = "# Картка за карткою — для вибору"


class RouterAnswer(_Frozen):
    action: Literal["offer", "ask", "choose", "answer"]
    profile: Profile
    candidates: list[Candidate]
    card_id: str | None
    reply: str | None
    why: str
    deep_question: str | None = None

    @field_validator("deep_question")
    @classmethod
    def _trimmed(cls, value: str | None) -> str | None:
        return clean_question(value)

    @model_validator(mode="after")
    def _fits_its_action(self) -> "RouterAnswer":
        ids = [c.card_id for c in self.candidates]
        if len(ids) > 3 or len(set(ids)) != len(ids):
            raise ValueError("at most 3 different candidates")
        if self.action == "offer" and (len(ids) < 2 or not (self.reply or "").strip()):
            raise ValueError("an offer needs 2–3 candidates and a reply")
        if self.action == "ask" and not (self.reply or "").strip():
            raise ValueError("an ask needs a reply")
        if self.action == "choose" and self.card_id is None:
            raise ValueError("a choose needs a card_id")
        if self.deep_question is not None and self.action != "answer":
            raise ValueError("a deep question goes only with an answer")
        if self.action == "answer" and self.card_id is not None:
            raise ValueError("an answer chooses no card")
        return self


def route(ctx: FacilitationContext, knowledge: CurrentKnowledge, llm: model.Llm) -> RouterAnswer:
    """Flow: instruction → frame → generate_json on the narrowed schema (one retry) → a plain RouterAnswer."""
    system = router_instruction(knowledge, ctx.language, ctx.spoken)
    contents, schema, rev = _contents(ctx), router_schema(knowledge), knowledge.rev_pair()
    answer = _twice(lambda: llm.generate_json(system, contents, schema, rev))
    return RouterAnswer.model_validate(answer.model_dump())


def router_schema(knowledge: CurrentKnowledge) -> type[RouterAnswer]:
    """RouterAnswer with every card_id narrowed to the ids of the current revision."""
    ids: Any = Literal[tuple(sorted(knowledge.cards))]
    candidate = create_model("RouterCandidate", __base__=Candidate, card_id=(ids, ...))
    return create_model(
        "RouterAnswerSchema",
        __base__=RouterAnswer,
        candidates=(cast(Any, list.__class_getitem__(candidate)), ...),
        card_id=(ids | None, ...),
    )


def router_instruction(knowledge: CurrentKnowledge, language: str | None, spoken: bool = False) -> str:
    """The router rules, the person's language, whether they listen, then the router half of every card."""
    cards = "\n\n".join(_card_text(card) for _, card in sorted(knowledge.cards.items()))
    rules = f"{ROUTER_RULES}\n\n# Мова відповіді\n{language_rule(language)}\n{listening_rule(spoken)}"
    return f"{rules}\n{CARDS_HEAD}\n{cards}\n"


def _card_text(card: Card) -> str:
    half = card.router
    lines = [
        f"### {card.id} — {card.title}",
        *([f"Метод: {card.method}"] if card.method else []),
        f"Потрібно на вході: {half.needs}",
        "Коли так:",
        *(f"- {item}" for item in half.when_yes),
        "Коли ні:",
        *(f"- {item}" for item in half.when_no),
        "Ознаки:",
        *(f"- {item}" for item in half.signals),
    ]
    return "\n".join(lines)


def _contents(ctx: FacilitationContext) -> list[model.Turn]:
    """The session's history as the facilitator sees it, then one frame: routing state, map, the turn."""
    frame = (
        f"[Стан вибору способу]\n{_routing_state(ctx.routing or ())}\n\n"
        f"[Карта проблеми зараз]\n{ctx.problem_map.model_dump_json()}\n\n"
        f"[Репліка людини #{ctx.turn_no}]\n{ctx.text}"
    )
    return [*(model.Turn(t.role, t.text) for t in ctx.history), model.Turn("user", frame)]


def _routing_state(routing: Sequence[Decision]) -> str:
    if not routing:
        return "(у цій темі ще не обирали способу думати)"
    return "\n".join(_decision_line(d) for d in routing)


def _decision_line(d: Decision) -> str:
    if d.kind == "end":
        how = "пройдено" if d.end == "done" else "не підходить"
        return f"- репліка #{d.turn}: end {d.card_id} — {d.end} ({how})"
    if d.kind == "choose":
        return f"- репліка #{d.turn}: choose {d.card_id} (людина обрала)"
    if d.kind == "answer":
        return f"- репліка #{d.turn}: answer (відповідь фактом)"
    if d.kind == "offer":
        return f"- репліка #{d.turn}: offer {', '.join(c.card_id for c in d.candidates)} (запропоновано)"
    return f"- репліка #{d.turn}: ask (уточнювальне питання)"


def _twice[M](call: Callable[[], M]) -> M:
    """One retry of an invalid answer; invalid twice → FacilitationError."""
    for attempt in (1, 2):
        try:
            return call()
        except ValidationError as exc:
            if attempt == 2:
                raise FacilitationError("the router's answer stayed invalid after one retry") from exc
    raise AssertionError("unreachable")
