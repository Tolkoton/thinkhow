"""Helpers for the one-conversation contract tests (slice tester). Built from the contract
`.engine/slices/one-conversation.md` and the public signatures, not the code.

The sealed helpers of earlier slices are reused as they are (their folders are put on `sys.path`):
`ca_fakes` (continuous-analysis: topics through `reply`, legacy conversation.md, FakeLlm, log capture),
`stp_fakes` (step-results: the chosen step and the injected `Question` of S6) and `rt_fakes`/`rt_cards`
(router: RouterLlm, cards, router answers).

- Fac: a `Facilitate` double; each call takes the next planned answer (a string, or None: the model fails
  with `Down`) and records the `FacilitationContext` it was given.
- T(role, text): the facilitation `Turn` a history holds.
"""

from __future__ import annotations

import sys
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
for sibling in ("continuous_analysis", "step_results", "router"):
    path = str(HERE.parent / sibling)
    if path not in sys.path:
        sys.path.insert(0, path)

import ca_fakes as ca  # noqa: E402
import rt_cards as rtc  # noqa: E402
import rt_fakes as rt  # noqa: E402
import stp_fakes as stp  # noqa: E402

from thinkhow.access import CurrentUser  # noqa: E402
from thinkhow.facilitation.types import (  # noqa: E402
    FacilitationContext,
    FacilitatorUpdate,
    MapUpdate,
    ReplyDelta,
)
from thinkhow.facilitation.types import Turn as T  # noqa: E402
from thinkhow.platform.storage import LocalStorage  # noqa: E402
from thinkhow.workspace import ReplyEvent, TopicRef, reply, retry  # noqa: E402

__all__ = ["T", "Fac", "Down", "ca", "rt", "rtc", "stp", "ask_reply", "again"]


class Down(Exception):
    """The facilitator's model failed: the person's turn stays without an answer."""


@dataclass
class Fac:
    answers: list[str | None] = field(default_factory=list)
    updates: Sequence[MapUpdate] = ()
    contexts: list[FacilitationContext] = field(default_factory=list)

    def __call__(self, context: FacilitationContext) -> Iterator[Any]:
        self.contexts.append(context)
        if not self.answers:
            raise AssertionError("facilitate was called more times than the scenario planned")
        return self._run(self.answers.pop(0))

    def _run(self, answer: str | None) -> Iterator[Any]:
        if answer is None:
            raise Down("down")
        yield ReplyDelta(text=answer)
        yield FacilitatorUpdate(
            reply=answer, current_phase_id=None, phase_exit_met=False, map_updates=list(self.updates)
        )


def ask_reply(
    storage: LocalStorage,
    fac: Any,
    user: CurrentUser,
    ref: TopicRef,
    text: str,
    at: datetime,
    question: Any = None,
) -> list[ReplyEvent]:
    """`reply`, drained."""
    if question is None:
        return list(reply(storage, fac, user, ref, text, at))
    return list(reply(storage, fac, user, ref, text, at, question=question))


def again(
    storage: LocalStorage, fac: Any, user: CurrentUser, ref: TopicRef, at: datetime
) -> list[ReplyEvent]:
    """`retry`, drained."""
    return list(retry(storage, fac, user, ref, at))
