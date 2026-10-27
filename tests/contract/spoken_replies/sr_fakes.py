"""Helpers for the spoken-replies contract tests (slice tester). Built from the contract, not the code.

- Cards, memory and knowledge: hand-built inputs from the I1/I2 «Domain» (a card without and with «method»,
  memory empty and not, languages None / a listed one / a non-Latin one).
- HEAD, LISTENING_HEAD: the two section headers named by the contract.
- ScenarioLlm: a fake `platform.llm.Llm` that records the system instruction of every call.
- ScenarioFacilitate: a `Facilitate` double that records every `FacilitationContext`.
- make_app: `create_app(Deps(...))` over a local folder with the given `facilitate`.

The Seam 1 oracle lives in `sr_oracle.py`: the strings the four functions returned at commit cefcb02
(before the slice), written out as literals.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from thinkhow.access import CurrentUser
from thinkhow.facilitation.types import (
    Candidate,
    Decision,
    FacilitationContext,
    FacilitatorUpdate,
    ReplyDelta,
    ResearchEvent,
    Rev,
    RoutingEvent,
    Source,
)
from thinkhow.knowledge import Card, CurrentKnowledge, MemoryRecord
from thinkhow.platform import llm as pl

HEAD = "# Мова відповіді\n"
LISTENING_HEAD = "# Людина слухає"

LANGUAGES: tuple[str | None, ...] = (None, "Polski (pl-PL)", "日本語 (ja-JP)")
T0 = datetime(2026, 10, 27, 12, 0, 0, tzinfo=UTC)


def _phase(pid: str) -> dict[str, Any]:
    return {
        "id": pid,
        "title": f"Фаза {pid}",
        "goal": f"мета {pid}",
        "how": [f"як {pid}"],
        "exit": f"вихід {pid}",
    }


def card(cid: str, phase_ids: Iterable[str], method: str | None = None) -> Card:
    data: dict[str, Any] = {
        "id": cid,
        "title": f"Картка {cid}",
        "router": {
            "needs": f"потреба {cid}",
            "when_yes": [f"так {cid}"],
            "when_no": [f"ні {cid}"],
            "signals": [f"сигнал {cid}"],
        },
        "facilitator": {
            "purpose": f"навіщо {cid}",
            "stance": f"позиція {cid}",
            "needs": f"на вході {cid}",
            "phases": [_phase(p) for p in phase_ids],
            "ending": f"кінець {cid}",
            "traps": [{"name": f"пастка {cid}", "text": f"текст пастки {cid}"}],
            "pairs_well": f"пара {cid}",
        },
    }
    if method is not None:
        data["method"] = method
    return Card.model_validate(data)


ALPHA = card("alpha", ["a_one", "a_two"])
BETA = card("beta", ["b_one"], method="Метод бета (Автор, 1999)")
CARDS = {"alpha": ALPHA, "beta": BETA}
MEMORY = [
    MemoryRecord(
        id="M-1",
        title="Досвід",
        cards=["alpha"],
        noticed="людина поспішає",
        do="повернути до фази",
        basis="3 сесії.",
    )
]
MEMORIES: dict[str, list[MemoryRecord]] = {"empty": [], "one": MEMORY}


def knowledge(
    cards: Sequence[Card] = (ALPHA, BETA), memory: list[MemoryRecord] | None = None
) -> CurrentKnowledge:
    return CurrentKnowledge(
        rev=3, n=7, cards={c.id: c for c in cards}, memory=list(MEMORY if memory is None else memory)
    )


KNOWLEDGES: dict[str, tuple[Card, ...]] = {"both": (ALPHA, BETA), "beta": (BETA,)}
DEEP_RULES = ("План", "Пошук", "Звіт")


# --- keys of the oracle -------------------------------------------------------------------------


def respond_key(card_id: str, memory: str, language: str | None, routed: bool) -> str:
    return f"respond|{card_id}|{memory}|{language}|{routed}"


def route_key(cards: str, language: str | None) -> str:
    return f"route|{cards}|{language}"


def answer_key(language: str | None) -> str:
    return f"answer|{language}"


def deep_key(rule: str, language: str | None) -> str:
    return f"deep|{rule}|{language}"


# --- the model double ---------------------------------------------------------------------------


@dataclass
class ScenarioLlm:
    deltas: list[str] = field(default_factory=list)
    done_raw: str = ""
    generate: list[str] = field(default_factory=list)
    stream_systems: list[str] = field(default_factory=list)
    generate_systems: list[str] = field(default_factory=list)

    def stream_json(
        self, system: str, contents: Sequence[pl.Turn], schema: type[BaseModel], rev: pl.KnowledgeRev | None
    ) -> Iterator[pl.ReplyDelta | pl.Done]:
        self.stream_systems.append(system)
        return self._stream()

    def _stream(self) -> Iterator[pl.ReplyDelta | pl.Done]:
        for step in self.deltas:
            yield pl.ReplyDelta(text=step)
        yield pl.Done(
            raw_json=self.done_raw, usage=pl.Usage(prompt_tokens=10, output_tokens=5, thought_tokens=0)
        )

    def generate_json(
        self, system: str, contents: Sequence[pl.Turn], schema: type[Any], rev: pl.KnowledgeRev | None
    ) -> Any:
        self.generate_systems.append(system)
        if not self.generate:
            raise AssertionError("generate_json was called more times than the scenario planned")
        return schema.model_validate_json(self.generate.pop(0))

    def search_text(
        self, system: str, prompt: str, rev: pl.KnowledgeRev | None
    ) -> tuple[str, pl.Found | None]:
        raise AssertionError("search_text is not part of these scenarios")


def lead_answer(reply: str, phase: str) -> str:
    return json.dumps(
        {"reply": reply, "current_phase_id": phase, "phase_exit_met": False, "map_updates": []},
        ensure_ascii=False,
    )


def fact_answer(reply: str) -> str:
    return json.dumps({"reply": reply, "map_updates": []}, ensure_ascii=False)


UNCLEAR_PROFILE = {
    k: "unclear"
    for k in ("intent", "structuredness", "reversibility", "stakes", "data", "options", "emotion", "social")
}


def router_ask(reply: str = "Що саме вас турбує?") -> str:
    return json.dumps(
        {
            "action": "ask",
            "profile": UNCLEAR_PROFILE,
            "candidates": [],
            "card_id": None,
            "reply": reply,
            "why": "мало даних",
        },
        ensure_ascii=False,
    )


def drain(it: Iterator[Any]) -> list[Any]:
    return list(it)


def snapshot(root: Path) -> dict[str, bytes]:
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


# --- workspace and web side ---------------------------------------------------------------------

ALICE = CurrentUser(id="alice-1", email="alice@example.com", is_owner=False)
IAP = "x-goog-iap-jwt-assertion"
TOKENS: dict[str, dict[str, str]] = {
    "tok-alice": {"sub": "accounts.google.com:alice-1", "email": "alice@example.com"},
}
H_ALICE = {IAP: "tok-alice"}

Step = str | FacilitatorUpdate | RoutingEvent | ResearchEvent | BaseException


@dataclass
class ScenarioFacilitate:
    scripts: list[list[Step]] = field(default_factory=list)
    contexts: list[FacilitationContext] = field(default_factory=list)

    def __call__(
        self, ctx: FacilitationContext
    ) -> Iterator[ReplyDelta | FacilitatorUpdate | RoutingEvent | ResearchEvent]:
        self.contexts.append(ctx)
        if not self.scripts:
            raise AssertionError("facilitate was called more times than the scenario planned")
        return self._run(self.scripts.pop(0))

    def _run(
        self, script: list[Step]
    ) -> Iterator[ReplyDelta | FacilitatorUpdate | RoutingEvent | ResearchEvent]:
        for step in script:
            if isinstance(step, BaseException):
                raise step
            if isinstance(step, str):
                yield ReplyDelta(text=step)
            else:
                yield step


def ok(reply: str = "Що може піти не так?") -> list[Step]:
    return [
        reply,
        FacilitatorUpdate(reply=reply, current_phase_id="p1", phase_exit_met=False, map_updates=[]),
    ]


def fail() -> list[Step]:
    return [pl.LlmUnavailable("down")]


def rich(turn: int, reply: str = "Ціна — близько 300 євро.") -> list[Step]:
    """A turn that leaves every file of a topic behind: a routing decision, a search, the answer."""
    decision = Decision(
        turn=turn,
        rev=Rev(rev=3, n=7),
        kind="choose",
        profile=None,
        candidates=[Candidate(card_id="alpha", why="підходить")],
        card_id="alpha",
        end=None,
        why="людина обрала",
    )
    research = ResearchEvent(
        depth="quick",
        queries=("ціна",),
        sources=(Source(title="ADAC", url="https://www.adac.de/x"),),
        suggestions_html=None,
    )
    return [
        RoutingEvent(decision),
        research,
        reply,
        FacilitatorUpdate(reply=reply, current_phase_id="a_one", phase_exit_met=False, map_updates=[]),
    ]


def verify_fake(token: str, audience: str) -> Any:
    if token not in TOKENS:
        raise RuntimeError("bad signature")
    return TOKENS[token]


def make_client(tmp_path: Path, facilitate: Any) -> tuple[Any, Any]:
    from fastapi.testclient import TestClient

    from thinkhow.platform.config import load_settings
    from thinkhow.platform.identity import IapIdentity
    from thinkhow.platform.speech import ScriptedSpeech
    from thinkhow.platform.storage import LocalStorage
    from thinkhow.web.server import Deps, create_app

    store = LocalStorage(tmp_path / "data")
    settings = load_settings(
        {
            "THINKHOW_LOCAL": "true",
            "THINKHOW_LOCAL_DIR": str(tmp_path),
            "THINKHOW_OWNER_EMAIL": "owner@example.com",
        }
    )
    deps = Deps(
        storage=store,
        identity=IapIdentity("aud-test", verify_fake),
        settings=settings,
        facilitate=facilitate,
        now=lambda: T0,
        speech=ScriptedSpeech("текст"),
    )
    client = TestClient(create_app(deps), raise_server_exceptions=False, follow_redirects=False)
    return client, store
