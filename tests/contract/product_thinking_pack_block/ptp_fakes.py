"""Helpers for the block tests of product-thinking-pack (slice tester, mode `block`).

Built from `.engine/architecture/feature/product-thinking-pack.md`, the two slice contracts it names and the
public signatures — not from the bodies. The fake product model (`Model`), the fake person (`Person`) and the
raw answers of the router and the facilitator are copied from the thinking-models-router block
(`tmr_fakes`): the same ports, the same F6 schema, the same scripts of task 302 (the feature: «Будова — та
сама»). Router calls (`generate_json` with a `RouterAnswer` schema) and facilitator calls (`stream_json`)
are answered by policies that get the number and the text of the person's turn (`[Репліка людини #N]`).
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType
from typing import Any

from pydantic import BaseModel

from thinkhow.access import CurrentUser
from thinkhow.facilitation import RouterAnswer
from thinkhow.knowledge import CurrentKnowledge, current, seed
from thinkhow.platform import llm as pl
from thinkhow.platform.storage import LocalStorage

ROOT = Path(__file__).resolve().parents[3]
CARDS = ROOT / "cards"
CASES = ROOT / "tests" / "fixtures" / "routing" / "cases.yaml"
ARTIFACTS = ROOT / ".engine" / "artifacts"
T0 = datetime(2026, 10, 24, 10, 0, 0, tzinfo=UTC)
ALICE = CurrentUser(id="alice-1", email="alice@example.com", is_owner=False)

CARD_IDS = sorted(p.stem for p in CARDS.glob("*.yaml"))

PROFILE: dict[str, str] = {
    "intent": "choose_between_options",
    "structuredness": "ill_structured",
    "reversibility": "one_way_door",
    "stakes": "high",
    "data": "qualitative_only",
    "options": "binary_dilemma",
    "emotion": "anxious",
    "social": "individual_personal",
}
OFFER_REPLY = (
    "Я зрозумів так: ви вагаєтесь, що робити далі. "
    "1) розкласти все по поличках; 2) глянути інакше. Що ближче?"
)
ASK_REPLY = "Що вам зараз важливіше — зрозуміти, що сталося, чи вирішити, що робити?"
ROUTER_WHY = "так вирішено за профілем"


def why_of(cid: str) -> str:
    return f"Це допоможе побачити вашу ситуацію з іншого боку ({cid})."


def at(minutes: int) -> datetime:
    return T0 + timedelta(minutes=minutes)


def script(name: str) -> ModuleType:
    """`scripts/<name>.py` by path (the scripts are not a package)."""
    key = f"ptp_script_{name}"
    if key not in sys.modules:
        spec = importlib.util.spec_from_file_location(key, ROOT / "scripts" / f"{name}.py")
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[key] = module
        spec.loader.exec_module(module)
    return sys.modules[key]


def seeded_knowledge(tmp: Path) -> tuple[LocalStorage, CurrentKnowledge]:
    store = LocalStorage(tmp)
    seed(store, CARDS)
    return store, current(store)


# --- raw answers (as the model returns them) --------------------------------------------------------------


def router_raw(
    action: str, candidates: Sequence[str] = (), card_id: str | None = None, reply: str | None = None
) -> str:
    return json.dumps(
        {
            "action": action,
            "profile": PROFILE,
            "candidates": [{"card_id": c, "why": why_of(c)} for c in candidates],
            "card_id": card_id,
            "reply": reply,
            "why": ROUTER_WHY,
        },
        ensure_ascii=False,
    )


def offer_raw(*ids: str) -> str:
    return router_raw("offer", ids, None, OFFER_REPLY)


def choose_raw(cid: str) -> str:
    return router_raw("choose", (), cid, None)


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


# --- the fake product model --------------------------------------------------------------------------------


@dataclass
class Call:
    kind: str  # "router" or "stream"
    system: str
    frame: str
    turn_no: int
    text: str


Policy = Callable[[int, str], str]


@dataclass
class Model:
    router: Policy = lambda no, text: offer_raw("issue-tree", "five-whys")
    facilitator: Policy = lambda no, text: fac_raw(None)
    calls: list[Call] = field(default_factory=list)

    def _record(self, kind: str, system: str, contents: Sequence[pl.Turn]) -> Call:
        frame = contents[-1].text
        no, text = person_turn(frame)
        call = Call(kind, system, frame, no, text)
        self.calls.append(call)
        return call

    def generate_json(
        self, system: str, contents: Sequence[pl.Turn], schema: type[Any], rev: pl.KnowledgeRev | None
    ) -> Any:
        call = self._record("router", system, contents)
        assert isinstance(schema, type) and issubclass(schema, RouterAnswer), schema
        return schema.model_validate_json(self.router(call.turn_no, call.text))

    def stream_json(
        self, system: str, contents: Sequence[pl.Turn], schema: type[BaseModel], rev: pl.KnowledgeRev | None
    ) -> Iterator[pl.ReplyDelta | pl.Done]:
        call = self._record("stream", system, contents)
        raw = self.facilitator(call.turn_no, call.text)
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


@dataclass
class Person:
    text: str = "Мені важливо розібратися, що робити далі."
    calls: int = 0

    def generate_json(
        self, system: str, contents: Sequence[pl.Turn], schema: type[Any], rev: pl.KnowledgeRev | None
    ) -> Any:
        self.calls += 1
        return schema.model_validate({"reply": self.text})

    def stream_json(
        self, system: str, contents: Sequence[pl.Turn], schema: type[BaseModel], rev: pl.KnowledgeRev | None
    ) -> Iterator[pl.ReplyDelta | pl.Done]:
        raise AssertionError("the synthetic person speaks through generate_json")


# The 7 ids of the feature's Goal, in its order.
NEW_IDS = [
    "customer-interviews", "demand-test", "positioning", "offer-design", "value-pricing", "traction-channels",
    "unit-economics",
]  # fmt: skip
# The case prefixes of the new cards in cases.yaml (S1 delivers 1: `*-3` is the held-out part).
PREFIX = {
    "customer-interviews": "ci",
    "demand-test": "dt",
    "positioning": "pos",
    "offer-design": "of",
    "value-pricing": "vp",
    "traction-channels": "tc",
    "unit-economics": "ue",
}
# The commit at which S1 was closed and S2's contract sealed (the request's base): S2 starts from here.
S1_CLOSED = "82e6213"
# The base of «Не гірше» (feature, Acceptance criteria).
BASE_RUN = ARTIFACTS / "router-eval" / "2026-10-25T180821Z.json"


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout


def live_normalise() -> Callable[[str], str]:
    """The normalisation of the live name detector, the one the sealed 6-word test uses."""
    key = "ptp_router_live"
    if key not in sys.modules:
        spec = importlib.util.spec_from_file_location(key, ROOT / "tests" / "live" / "test_router_live.py")
        assert spec is not None and spec.loader is not None
        module: ModuleType = importlib.util.module_from_spec(spec)
        sys.modules[key] = module
        spec.loader.exec_module(module)
    normalise: Callable[[str], str] = sys.modules[key].normalise
    return normalise
