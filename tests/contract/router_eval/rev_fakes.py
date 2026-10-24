"""Helpers for the router-eval contract tests (slice tester; built from the contract, not the code).

- `script(name)`: loads `scripts/<name>.py` by path (the scripts are not a package).
- `knowledge(tmp)`: the 18 cards of `cards/` seeded into a temporary `LocalStorage` (product path `seed`).
- `ProductLlm`: a fake product model port. Router calls (`generate_json` with a `RouterAnswer` schema) and
  facilitator calls (`stream_json`) are answered by policies keyed on the person's turn and its text, read
  from the frame of the call; every call is recorded with the log's request id of the calling thread.
  The frame numbers every turn of the topic (the person's turns are #1, #3, #5…), so the policies get the
  ordinal of the person's turn, `(turn_no + 1) // 2`: 1 for the opener, 2 for the next one, and so on.
- `PersonLlm`: a fake synthetic person (`generate_json`, schema `{reply: str}`).
- Raw answers of the router and of the facilitator, written by hand from the contract.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
import threading
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any

from pydantic import BaseModel

from thinkhow.facilitation import RouterAnswer
from thinkhow.knowledge import CurrentKnowledge, current, seed
from thinkhow.platform import llm as pl
from thinkhow.platform import log as plog
from thinkhow.platform.storage import LocalStorage

ROOT = Path(__file__).resolve().parents[3]
CARDS = ROOT / "cards"
CASES = ROOT / "tests" / "fixtures" / "routing" / "cases.yaml"
OWNER = ROOT / "tests" / "fixtures" / "facilitator_free_mode" / "owner_topic.json"
STAMP = "2026-10-24T180000Z"

_loaded: dict[str, ModuleType] = {}


def script(name: str) -> ModuleType:
    if name not in _loaded:
        spec = importlib.util.spec_from_file_location(f"rev_script_{name}", ROOT / "scripts" / f"{name}.py")
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        _loaded[name] = module
    return _loaded[name]


def live_detector() -> Callable[[str], bool]:
    spec = importlib.util.spec_from_file_location(
        "rev_router_live", ROOT / "tests" / "live" / "test_router_live.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.names_a_method  # type: ignore[no-any-return]


def live_normalise() -> Callable[[str], str]:
    live_detector()
    return sys.modules["rev_router_live"].normalise  # type: ignore[no-any-return]


def knowledge(tmp: Path) -> CurrentKnowledge:
    store = LocalStorage(tmp)
    seed(store, CARDS)
    return current(store)


PROFILE: dict[str, str] = {
    "intent": "find_cause",
    "structuredness": "moderately_structured",
    "reversibility": "two_way_door",
    "stakes": "medium",
    "data": "qualitative_only",
    "options": "unclear",
    "emotion": "neutral_analytical",
    "social": "product_or_team",
}
OFFER_REPLY = "Я зрозумів так: вам треба розібратися. 1) спокійно розкласти; 2) подивитися ширше. Що ближче?"
ASK_REPLY = "Що для вас зараз важливіше — зрозуміти, що сталося, чи вирішити, що робити?"


def answer_dict(
    action: str, candidates: Sequence[str] = (), card_id: str | None = None, reply: str | None = None
) -> dict[str, Any]:
    return {
        "action": action,
        "profile": PROFILE,
        "candidates": [{"card_id": c, "why": f"Це допоможе ({c})."} for c in candidates],
        "card_id": card_id,
        "reply": reply,
        "why": "так вирішено за профілем",
    }


def offer_raw(*ids: str) -> str:
    return json.dumps(answer_dict("offer", ids, None, OFFER_REPLY), ensure_ascii=False)


def ask_raw(*ids: str) -> str:
    return json.dumps(answer_dict("ask", ids, None, ASK_REPLY), ensure_ascii=False)


def choose_raw(cid: str) -> str:
    return json.dumps(answer_dict("choose", (), cid, None), ensure_ascii=False)


def invalid_raw() -> str:
    """An offer with one candidate: refused by the router schema (an offer needs 2–3)."""
    return json.dumps(answer_dict("offer", ("five-whys",), None, OFFER_REPLY), ensure_ascii=False)


def answer(action: str, candidates: Sequence[str] = (), card_id: str | None = None) -> RouterAnswer:
    reply = None if action == "choose" else (OFFER_REPLY if action == "offer" else ASK_REPLY)
    return RouterAnswer.model_validate(answer_dict(action, candidates, card_id, reply))


def fac_raw(phase: str | None, exit_met: bool = False, reply: str = "Що для вас тут головне?") -> str:
    return json.dumps(
        {"reply": reply, "current_phase_id": phase, "phase_exit_met": exit_met, "map_updates": []},
        ensure_ascii=False,
    )


_TURN = re.compile(r"\[Репліка людини #(\d+)\]\n(.*)\Z", re.S)


def person_turn(frame: str) -> tuple[int, str]:
    m = _TURN.search(frame)
    assert m is not None, frame[-300:]
    return int(m.group(1)), m.group(2)


def routing_lines(frame: str) -> list[str]:
    head = "[Стан вибору способу]\n"
    assert head in frame, frame[:300]
    block = frame.split(head, 1)[1].split("\n\n[Карта проблеми зараз]", 1)[0]
    return [line for line in block.splitlines() if line.strip()]


@dataclass
class Call:
    kind: str  # "router" or "stream"
    system: str
    frame: str
    turn_no: int
    text: str
    request_id: str | None

    @property
    def index(self) -> int:
        """The ordinal of the person's turn (the frame's #1, #3, #5… → 1, 2, 3…)."""
        return (self.turn_no + 1) // 2


RouterPolicy = Callable[[int, str], str]
FacPolicy = Callable[[int, str], str]


@dataclass
class ProductLlm:
    router: RouterPolicy
    facilitator: FacPolicy = lambda no, text: fac_raw(None)
    calls: list[Call] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def _record(self, kind: str, system: str, contents: Sequence[pl.Turn]) -> Call:
        frame = contents[-1].text
        no, text = person_turn(frame)
        call = Call(kind, system, frame, no, text, plog.request_id.get())
        with self.lock:
            self.calls.append(call)
        return call

    def generate_json(
        self, system: str, contents: Sequence[pl.Turn], schema: type[Any], rev: pl.KnowledgeRev | None
    ) -> Any:
        call = self._record("router", system, contents)
        assert isinstance(schema, type) and issubclass(schema, RouterAnswer), schema
        return schema.model_validate_json(self.router(call.index, call.text))

    def stream_json(
        self, system: str, contents: Sequence[pl.Turn], schema: type[BaseModel], rev: pl.KnowledgeRev | None
    ) -> Iterator[pl.ReplyDelta | pl.Done]:
        call = self._record("stream", system, contents)
        raw = self.facilitator(call.index, call.text)
        return iter(
            [
                pl.ReplyDelta(text=json.loads(raw)["reply"]),
                pl.Done(raw_json=raw, usage=pl.Usage(prompt_tokens=10, output_tokens=5, thought_tokens=0)),
            ]
        )

    @property
    def router_calls(self) -> list[Call]:
        return [c for c in self.calls if c.kind == "router"]

    @property
    def stream_calls(self) -> list[Call]:
        return [c for c in self.calls if c.kind == "stream"]

    def person_turns(self) -> dict[int, str]:
        """The person's turns the product saw, by their ordinal (1 = the opener)."""
        return {c.index: c.text for c in self.calls}


PERSON_DEFAULT = "Мені важливо розібратися, що робити далі."


@dataclass
class PersonLlm:
    replies: list[str] = field(default_factory=list)
    calls: list[str] = field(default_factory=list)

    def generate_json(
        self, system: str, contents: Sequence[pl.Turn], schema: type[Any], rev: pl.KnowledgeRev | None
    ) -> Any:
        self.calls.append(system)
        text = self.replies.pop(0) if self.replies else PERSON_DEFAULT
        return schema.model_validate({"reply": text})

    def stream_json(
        self, system: str, contents: Sequence[pl.Turn], schema: type[BaseModel], rev: pl.KnowledgeRev | None
    ) -> Iterator[pl.ReplyDelta | pl.Done]:
        raise AssertionError("the synthetic person speaks through generate_json")


class Down(Exception):
    """A model failure inside the facilitator's stream (workspace answers it with Failed(\"Down\"))."""
