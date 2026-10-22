"""Helpers for the skel-facilitation contract tests (slice tester). Built from the contract, not the code.

- ScenarioLlm: a fake of the `platform.llm.Llm` protocol (not ScriptedLlm). `stream_json` yields the
  planned `platform.llm.ReplyDelta`s (or raises a planned exception at that point), then one `Done`
  with the planned raw JSON. `generate_json` validates the planned raw JSON by the schema it was given
  (`schema.model_validate_json`, so an invalid answer raises pydantic's ValidationError, as the
  contract names), or raises a planned exception. Every call is recorded.
- card / knowledge / context: valid inputs built by hand.
- collect: runs and drains `respond`, returning what it yielded and the exception it ended with (or None).
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

from thinkhow.facilitation.types import FacilitationContext, MapItem, ProblemMap, Turn
from thinkhow.knowledge import Card, CurrentKnowledge, MemoryRecord
from thinkhow.platform import llm as pl

Step = str | BaseException


@dataclass
class Call:
    system: str
    contents: list[pl.Turn]
    schema: type[BaseModel]
    rev: pl.KnowledgeRev | None


@dataclass
class ScenarioLlm:
    deltas: list[Step] = field(default_factory=list)
    done_raw: str = ""
    generate: list[Step] = field(default_factory=list)
    stream_calls: list[Call] = field(default_factory=list)
    generate_calls: list[Call] = field(default_factory=list)

    def stream_json(
        self, system: str, contents: Sequence[pl.Turn], schema: type[BaseModel], rev: pl.KnowledgeRev | None
    ) -> Iterator[pl.ReplyDelta | pl.Done]:
        self.stream_calls.append(Call(system, list(contents), schema, rev))
        return self._stream()

    def _stream(self) -> Iterator[pl.ReplyDelta | pl.Done]:
        for step in self.deltas:
            if isinstance(step, BaseException):
                raise step
            yield pl.ReplyDelta(text=step)
        yield pl.Done(
            raw_json=self.done_raw, usage=pl.Usage(prompt_tokens=10, output_tokens=5, thought_tokens=0)
        )

    def generate_json(
        self, system: str, contents: Sequence[pl.Turn], schema: type[Any], rev: pl.KnowledgeRev | None
    ) -> Any:
        self.generate_calls.append(Call(system, list(contents), schema, rev))
        if not self.generate:
            raise AssertionError("generate_json was called more times than the scenario planned")
        step = self.generate.pop(0)
        if isinstance(step, BaseException):
            raise step
        return schema.model_validate_json(step)


def phase_dict(pid: str) -> dict[str, Any]:
    tag = pid.upper()
    return {
        "id": pid,
        "title": f"Фаза {tag}",
        "goal": f"мета фази {tag}",
        "how": [f"як фази {tag}"],
        "exit": f"вихід фази {tag}",
    }


def card(cid: str, phase_ids: Iterable[str]) -> Card:
    return Card.model_validate(
        {
            "id": cid,
            "title": f"Картка {cid}",
            "router": {
                "needs": f"роутер-потреба {cid}",
                "when_yes": [f"так {cid}"],
                "when_no": [f"ні {cid}"],
                "signals": [f"сигнал {cid}"],
            },
            "facilitator": {
                "purpose": f"навіщо {cid}",
                "stance": f"позиція {cid}",
                "needs": f"на вході {cid}",
                "phases": [phase_dict(p) for p in phase_ids],
                "ending": f"кінець {cid}",
                "traps": [{"name": f"пастка {cid}", "text": f"текст пастки {cid}"}],
                "pairs_well": f"пара {cid}",
            },
        }
    )


ALPHA = card("alpha", ["a_one", "a_two", "a_three"])
BETA = card("beta", ["b_one", "b_two"])

MEMORY = [
    MemoryRecord(
        id="M-1",
        title="Перший досвід",
        cards=["alpha", "beta"],
        noticed="людина поспішає до висновку",
        do="повернути до фази",
        basis="3 сесії.",
    ),
    MemoryRecord(
        id="M-2",
        title="Чужий досвід",
        cards=["gamma"],
        noticed="плутають етапи",
        do="назвати етап",
        basis="5 сесій.",
    ),
]


def knowledge(
    cards: Iterable[Card] = (ALPHA, BETA), memory: list[MemoryRecord] | None = None
) -> CurrentKnowledge:
    return CurrentKnowledge(
        rev=3, n=7, cards={c.id: c for c in cards}, memory=list(MEMORY if memory is None else memory)
    )


PROBLEM_MAP = ProblemMap(
    items=[MapItem(id="i1", type="plan", text="кав'ярня біля університету", turn="t1")],
    phase_id="a_one",
    last_turn=1,
)

HISTORY = [
    Turn(role="user", text="Хочу відкрити кав'ярню."),
    Turn(role="model", text="Який у вас план і за який строк?"),
]


def context(
    card_id: str = "alpha", turn_no: int = 3, text: str = "За пів року, біля університету."
) -> FacilitationContext:
    return FacilitationContext(
        card_id=card_id, history=list(HISTORY), problem_map=PROBLEM_MAP, turn_no=turn_no, text=text
    )


ADD = {"op": "add", "id": "i2", "type": "threat", "text": "оренда зросте", "turn": "t3"}


def answer(
    reply: str, phase: str, exit_met: bool = False, updates: list[dict[str, Any]] | None = None
) -> str:
    """A full answer with `reply` first (as the model streams it)."""
    return json.dumps(
        {"reply": reply, "current_phase_id": phase, "phase_exit_met": exit_met, "map_updates": updates or []},
        ensure_ascii=False,
    )


def answer_reply_last(reply: str, phase: str, exit_met: bool = False) -> str:
    """A full answer where `reply` is not the first field (no deltas come)."""
    return json.dumps(
        {"current_phase_id": phase, "phase_exit_met": exit_met, "map_updates": [], "reply": reply},
        ensure_ascii=False,
    )


def update_only(phase: str, exit_met: bool = False, updates: list[dict[str, Any]] | None = None) -> str:
    """The retry answer without `reply`."""
    return json.dumps(
        {"current_phase_id": phase, "phase_exit_met": exit_met, "map_updates": updates or []},
        ensure_ascii=False,
    )


def collect(start: Callable[[], Iterator[Any]]) -> tuple[list[Any], BaseException | None]:
    """Run `start()` and drain it; an exception raised by the call itself or while iterating ends it."""
    items: list[Any] = []
    try:
        for item in start():
            items.append(item)
    except NotImplementedError:
        raise  # no path of the contract raises it: an unbuilt respond must fail the test as itself
    except Exception as exc:  # the test inspects what ended the stream
        return items, exc
    return items, None
