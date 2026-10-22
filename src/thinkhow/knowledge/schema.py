"""The shape of the Knowledge: cards, memory records, change records (M1 «Знання», M2 S6). Pydantic v2.

Does NOT check a version (completeness, no people's details) — that is F11.
"""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Text = Annotated[str, StringConstraints(min_length=1)]


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Phase(_Frozen):
    id: Annotated[str, StringConstraints(pattern=r"^[a-z0-9_]{1,64}$")]
    title: str
    goal: Text
    how: list[str]
    skip_if: str | None = None
    exit: Text


class RouterHalf(_Frozen):
    needs: str
    when_yes: Annotated[list[str], Field(min_length=1)]
    when_no: Annotated[list[str], Field(min_length=1)]
    signals: list[str]


class Trap(_Frozen):
    name: str
    text: str


class FacilitatorHalf(_Frozen):
    purpose: str
    stance: str
    needs: str
    phases: Annotated[list[Phase], Field(min_length=1)]
    ending: str
    traps: list[Trap]
    pairs_well: str

    @model_validator(mode="after")
    def _distinct_phase_ids(self) -> "FacilitatorHalf":
        ids = [phase.id for phase in self.phases]
        if len(set(ids)) != len(ids):
            raise ValueError("phase ids of a card must differ")
        return self


class Card(_Frozen):
    id: Annotated[str, StringConstraints(pattern=r"^[a-z0-9-]{1,64}$")]
    title: str
    router: RouterHalf
    facilitator: FacilitatorHalf


class MemoryRecord(_Frozen):
    id: Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9-]{1,64}$")]
    title: str
    cards: list[str]
    noticed: str
    do: str
    basis: str


class ChangeRecord(_Frozen):
    rev: Annotated[int, Field(ge=1)]
    what: str
    why: str
    cards: dict[str, str]
    memory: dict[str, str]
