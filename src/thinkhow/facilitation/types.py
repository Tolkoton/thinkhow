"""The values facilitation exchanges with workspace and web (M3 A1). Plain values only:
this module imports neither thinkhow.knowledge nor thinkhow.platform (skel-facilitation Q6)."""

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Literal

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


@dataclass(frozen=True)
class FacilitationContext:
    card_id: str
    history: list[Turn]
    problem_map: ProblemMap
    turn_no: int
    text: str
    language: str | None = None


Facilitate = Callable[[FacilitationContext], Iterator[ReplyDelta | FacilitatorUpdate]]


class FacilitationError(Exception):
    """The model answered, but its update stayed invalid after the one retry of the update."""
