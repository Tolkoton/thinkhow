"""The values facilitation exchanges with workspace and web (M3 A1). Plain values only:
this module imports neither thinkhow.knowledge nor thinkhow.platform (skel-facilitation Q6)."""

from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

ItemType = Literal[
    "goal",
    "plan",
    "option_considered",
    "assumption",
    "missing",
    "blind_spot",
    "emotion",
    "change_mind",
    "threat",
    "mitigation",
    "tripwire",
    "chosen_step",
    "router_note",
    "fact",
]


@dataclass(frozen=True)
class Turn:
    role: Literal["user", "model"]
    text: str


@dataclass(frozen=True)
class ReplyDelta:
    text: str


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class MapItem(_Frozen):
    id: str
    type: ItemType
    text: str
    turn: str


class ProblemMap(_Frozen):
    items: list[MapItem] = []
    phase_id: str | None = None
    last_turn: int = 0


class MapUpdate(_Frozen):
    op: Literal["add", "update", "remove"]
    id: str
    type: ItemType
    text: str
    turn: str


class FacilitatorUpdate(_Frozen):
    reply: str = Field(min_length=1)
    current_phase_id: str | None
    phase_exit_met: bool
    map_updates: list[MapUpdate]


class FactAnswer(_Frozen):
    """A fact answered at once (the router's «answer»): the reply first, the map's changes."""

    reply: str = Field(min_length=1)
    map_updates: list[MapUpdate]


class FactUpdate(_Frozen):
    """The update-only retry of a fact answer: the map's changes alone."""

    map_updates: list[MapUpdate]


class DeepPlan(_Frozen):
    """The deep cycle's plan: one line to the person, then 2–4 sub-questions to search."""

    intro: str = Field(min_length=1)
    questions: list[Annotated[str, Field(min_length=1)]] = Field(min_length=2, max_length=4)


class DeepReport(_Frozen):
    """The deep cycle's report to the person and the facts it found (the code makes them map items)."""

    report: str = Field(min_length=1)
    facts: list[str]


class Profile(_Frozen):
    """The problem profile: the 8 dimensions of M1 (no «crisis» state — N3)."""

    intent: Literal[
        "understand_situation",
        "find_cause",
        "choose_between_options",
        "generate_ideas",
        "plan_execution",
        "stress_test",
        "predict_consequences",
        "reflect_on_experience",
        "overcome_block",
        "resolve_dilemma",
        "unclear",
    ]
    structuredness: Literal["well_structured", "moderately_structured", "ill_structured", "wicked", "unclear"]
    reversibility: Literal["one_way_door", "two_way_door", "unclear"]
    stakes: Literal["high", "medium", "low", "unclear"]
    data: Literal["data_rich", "qualitative_only", "data_poor_speculative", "unclear"]
    options: Literal[
        "none_exist", "single_ultimatum", "binary_dilemma", "multiple_clear", "too_many_unfiltered", "unclear"
    ]
    emotion: Literal[
        "neutral_analytical",
        "ambivalent",
        "anxious",
        "overwhelmed_fatigued",
        "overconfident_attached",
        "unclear",
    ]
    social: Literal["individual_personal", "interpersonal_dyad", "product_or_team", "unclear"]


class Candidate(_Frozen):
    card_id: str
    why: str = Field(min_length=1)


class Rev(_Frozen):
    rev: int
    n: int


class Decision(_Frozen):
    """One decision of the router in routing.json; `turn` is the person's turn it answered."""

    turn: int
    rev: Rev
    kind: Literal["offer", "ask", "choose", "end", "answer"]
    profile: Profile | None
    candidates: list[Candidate]
    card_id: str | None
    end: Literal["done", "not_fit"] | None
    why: str


@dataclass(frozen=True)
class RoutingEvent:
    decision: Decision


@dataclass(frozen=True)
class Source:
    title: str
    url: str


@dataclass(frozen=True)
class ResearchEvent:
    """What a search behind one answer found; workspace writes it into research.json (A7)."""

    depth: Literal["quick", "deep"]
    queries: tuple[str, ...]
    sources: tuple[Source, ...]
    suggestions_html: str | None
    question: str | None = None
    report: str | None = None


def clean_question(question: str | None) -> str | None:
    """A deep question trimmed; an empty or blank one is none (research-deep)."""
    text = (question or "").strip()
    return text or None


def current_card(routing: Sequence[Decision]) -> str | None:
    """The card of the last decision when it is a `choose`; otherwise none (the router is next)."""
    if routing and routing[-1].kind == "choose":
        return routing[-1].card_id
    return None


@dataclass(frozen=True)
class FacilitationContext:
    card_id: str
    history: list[Turn]
    problem_map: ProblemMap
    turn_no: int
    text: str
    language: str | None = None
    routing: tuple[Decision, ...] | None = field(default=None, compare=False)


Facilitate = Callable[
    [FacilitationContext], Iterator[ReplyDelta | FacilitatorUpdate | RoutingEvent | ResearchEvent]
]


class FacilitationError(Exception):
    """The model answered, but its update stayed invalid after the one retry of the update."""
