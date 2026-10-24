"""Helpers for the router contract tests (slice tester; built from the contract, not the code).

- RouterLlm: a fake `platform.llm.Llm`. `generate_json` validates the next planned raw JSON by the schema it
  was given (so an invalid planned answer is a `ValidationError` inside the call, as the contract says);
  `stream_json` yields the planned facilitator answer's `reply` as one delta, then `Done` with the raw JSON.
  Every call is recorded with its schema, so router calls (a subclass of `RouterAnswer`) can be counted.
- RecordingLead: a `lead` double for `converse` that records every context and yields its planned items.
- ScenarioFacilitate: a `Facilitate` double for `workspace.reply` that may yield `RoutingEvent`s.
- Builders of router answers (raw JSON) and of `Decision`s, written by hand from the contract «Seam».
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel
from rt_cards import ALPHA, BETA, GAMMA, HISTORY, MEMORY, problem_map

from thinkhow.access import CurrentUser
from thinkhow.facilitation.route import RouterAnswer
from thinkhow.facilitation.types import (
    Candidate,
    Decision,
    FacilitationContext,
    FacilitatorUpdate,
    ProblemMap,
    Profile,
    ReplyDelta,
    Rev,
    RoutingEvent,
    Turn,
)
from thinkhow.knowledge import Card, CurrentKnowledge
from thinkhow.platform import llm as pl
from thinkhow.platform.storage import LocalStorage
from thinkhow.workspace import TopicRef, create_topic

T0 = datetime(2026, 10, 24, 10, 0, 0, tzinfo=UTC)
ALICE = CurrentUser(id="alice-1", email="alice@example.com", is_owner=False)

REV = Rev(rev=3, n=7)
ROUTED_HEAD = "# Коли картку пройдено або вона не підходить"
FREE_MODE_LINE = "[Стан] Вільний режим уже триває: людина чула, що картка не підходить. Не кажи цього знову."
RULE_PL = (
    "Відповідай мовою людини — Polski (pl-PL): цю мову вона обрала для розмов з ThinkHow, "
    "і це правило важливіше за «мовою останньої репліки» вище. "
    "Іншою мовою — лише якщо людина прямо попросить. "
    "Ніколи не відповідай російською — ні на репліку російською, ні на прохання."
)
RULE_NONE = "Ніколи не відповідай російською: на репліку російською відповідай українською."

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
PROFILE_OBJ = Profile.model_validate(PROFILE)

OFFER_REPLY = "Я зрозумів так: ви вагаєтесь щодо кав'ярні. 1) … 2) … Котрий ближчий — чи інше?"
ASK_REPLY = "Що для вас зараз важливіше — зрозуміти, що сталося, чи вирішити, що робити?"


def why_of(cid: str) -> str:
    return f"Це допоможе побачити вашу ситуацію з іншого боку ({cid})."


# --- knowledge and contexts ---------------------------------------------------------------------------------


def knowledge(cards: Iterable[Card] = (ALPHA, BETA, GAMMA), rev: int = 3, n: int = 7) -> CurrentKnowledge:
    return CurrentKnowledge(rev=rev, n=n, cards={c.id: c for c in cards}, memory=list(MEMORY))


def context(
    routing: tuple[Decision, ...] | None,
    card_id: str = "alpha",
    pm: ProblemMap | None = None,
    turn_no: int = 3,
    text: str = "Боюся, що не вийде.",
    language: str | None = None,
    history: list[Turn] | None = None,
) -> FacilitationContext:
    return FacilitationContext(
        card_id=card_id,
        history=list(HISTORY if history is None else history),
        problem_map=pm if pm is not None else problem_map(None, 2),
        turn_no=turn_no,
        text=text,
        language=language,
        routing=routing,
    )


# --- router answers (raw JSON, as the model returns them) ---------------------------------------------------


def router_raw(
    action: str,
    candidates: Sequence[tuple[str, str]] = (),
    card_id: str | None = None,
    reply: str | None = None,
    why: str = "так вирішено за профілем",
) -> str:
    return json.dumps(
        {
            "action": action,
            "profile": PROFILE,
            "candidates": [{"card_id": c, "why": w} for c, w in candidates],
            "card_id": card_id,
            "reply": reply,
            "why": why,
        },
        ensure_ascii=False,
    )


def offer(*ids: str, reply: str = OFFER_REPLY, why: str = "пропоную за профілем") -> str:
    return router_raw("offer", [(i, why_of(i)) for i in ids], None, reply, why)


def ask(reply: str = ASK_REPLY, why: str = "без відповіді не розрізнити") -> str:
    return router_raw("ask", [], None, reply, why)


def choose(cid: str, why: str = "людина обрала перше") -> str:
    return router_raw("choose", [], cid, None, why)


# --- decisions (as routing.json holds them) -----------------------------------------------------------------


def d_offer(turn: int, *ids: str, rev: Rev = REV, why: str = "пропоную за профілем") -> Decision:
    return Decision(
        turn=turn,
        rev=rev,
        kind="offer",
        profile=PROFILE_OBJ,
        candidates=[Candidate(card_id=i, why=why_of(i)) for i in ids],
        card_id=None,
        end=None,
        why=why,
    )


def d_ask(turn: int, rev: Rev = REV, why: str = "без відповіді не розрізнити") -> Decision:
    return Decision(
        turn=turn, rev=rev, kind="ask", profile=PROFILE_OBJ, candidates=[], card_id=None, end=None, why=why
    )


def d_choose(turn: int, cid: str, rev: Rev = REV, why: str = "людина обрала перше") -> Decision:
    return Decision(
        turn=turn, rev=rev, kind="choose", profile=PROFILE_OBJ, candidates=[], card_id=cid, end=None, why=why
    )


def d_end(turn: int, cid: str, end: str, rev: Rev = REV) -> Decision:
    why = "картку пройдено" if end == "done" else "картка не підходить"
    return Decision.model_validate(
        {
            "turn": turn,
            "rev": rev.model_dump(),
            "kind": "end",
            "profile": None,
            "candidates": [],
            "card_id": cid,
            "end": end,
            "why": why,
        }
    )


def same_but_why(a: Decision, b: Decision) -> bool:
    """Equal in every field the contract fixes exactly; `why` of an `end` is checked apart (Q2)."""
    return a.model_dump(exclude={"why"}) == b.model_dump(exclude={"why"})


# --- the model double ---------------------------------------------------------------------------------------


@dataclass
class Call:
    kind: str  # "generate" or "stream"
    system: str
    contents: list[pl.Turn]
    schema: type[BaseModel]
    rev: pl.KnowledgeRev | None

    @property
    def is_router(self) -> bool:
        return isinstance(self.schema, type) and issubclass(self.schema, RouterAnswer)

    @property
    def frame(self) -> str:
        return self.contents[-1].text


@dataclass
class RouterLlm:
    generate: list[str] = field(default_factory=list)
    streams: list[str] = field(default_factory=list)
    calls: list[Call] = field(default_factory=list)

    @property
    def router_calls(self) -> list[Call]:
        return [c for c in self.calls if c.kind == "generate" and c.is_router]

    @property
    def stream_calls(self) -> list[Call]:
        return [c for c in self.calls if c.kind == "stream"]

    def stream_json(
        self, system: str, contents: Sequence[pl.Turn], schema: type[BaseModel], rev: pl.KnowledgeRev | None
    ) -> Iterator[pl.ReplyDelta | pl.Done]:
        self.calls.append(Call("stream", system, list(contents), schema, rev))
        if not self.streams:
            raise AssertionError("stream_json was called more times than the scenario planned")
        return self._stream(self.streams.pop(0))

    def _stream(self, raw: str) -> Iterator[pl.ReplyDelta | pl.Done]:
        try:
            text = json.loads(raw).get("reply")
        except ValueError:
            text = None
        if isinstance(text, str) and text:
            yield pl.ReplyDelta(text=text)
        yield pl.Done(raw_json=raw, usage=pl.Usage(prompt_tokens=10, output_tokens=5, thought_tokens=0))

    def generate_json(
        self, system: str, contents: Sequence[pl.Turn], schema: type[Any], rev: pl.KnowledgeRev | None
    ) -> Any:
        self.calls.append(Call("generate", system, list(contents), schema, rev))
        if not self.generate:
            raise AssertionError("generate_json was called more times than the scenario planned")
        return schema.model_validate_json(self.generate.pop(0))


def fac_answer(reply: str, phase: str | None, exit_met: bool = False) -> str:
    """A full facilitator answer, `reply` first."""
    return json.dumps(
        {"reply": reply, "current_phase_id": phase, "phase_exit_met": exit_met, "map_updates": []},
        ensure_ascii=False,
    )


def update(
    phase: str | None, exit_met: bool = False, reply: str = "Що для вас тут головне?"
) -> FacilitatorUpdate:
    return FacilitatorUpdate(reply=reply, current_phase_id=phase, phase_exit_met=exit_met, map_updates=[])


# --- the lead double (for converse) -------------------------------------------------------------------------

Item = ReplyDelta | FacilitatorUpdate | RoutingEvent


@dataclass
class RecordingLead:
    scripts: list[list[Item]] = field(default_factory=list)
    contexts: list[FacilitationContext] = field(default_factory=list)

    def __call__(
        self, ctx: FacilitationContext, knowledge: CurrentKnowledge, llm: pl.Llm
    ) -> Iterator[ReplyDelta | FacilitatorUpdate]:
        self.contexts.append(ctx)
        if not self.scripts:
            raise AssertionError("lead was called more times than the scenario planned")
        return self._run(self.scripts.pop(0))

    def _run(self, script: list[Item]) -> Iterator[Any]:
        yield from script


def led(phase: str | None, exit_met: bool = False, deltas: Sequence[str] = ("Що ", "далі?")) -> list[Item]:
    return [*(ReplyDelta(text=d) for d in deltas), update(phase, exit_met, "".join(deltas))]


# --- the workspace side -------------------------------------------------------------------------------------


@dataclass
class ScenarioFacilitate:
    scripts: list[list[Item | BaseException]] = field(default_factory=list)
    contexts: list[FacilitationContext] = field(default_factory=list)

    def __call__(self, ctx: FacilitationContext) -> Iterator[Item]:
        self.contexts.append(ctx)
        if not self.scripts:
            raise AssertionError("facilitate was called more times than the scenario planned")
        return self._run(self.scripts.pop(0))

    def _run(self, script: list[Item | BaseException]) -> Iterator[Item]:
        for step in script:
            if isinstance(step, BaseException):
                raise step
            yield step


class Down(Exception):
    """A model failure inside the stream (workspace answers it with Failed)."""


def topic(store: LocalStorage) -> TopicRef:
    return TopicRef(ALICE.id, create_topic(store, ALICE, "Тема", T0))


def routing_path(ref: TopicRef) -> str:
    return f"{ref.uid}/{ref.topic_id}/routing.json"


def raw_routing(store: LocalStorage, ref: TopicRef) -> bytes | None:
    return store.read("users", routing_path(ref))


def read_routing(store: LocalStorage, ref: TopicRef) -> list[Decision] | None:
    data = raw_routing(store, ref)
    if data is None:
        return None
    doc = json.loads(data)
    assert set(doc) == {"decisions"}, doc
    return [Decision.model_validate(d) for d in doc["decisions"]]


def put_routing(store: LocalStorage, ref: TopicRef, decisions: Sequence[Decision]) -> None:
    doc = {"decisions": [d.model_dump(mode="json") for d in decisions]}
    store.write("users", routing_path(ref), json.dumps(doc, ensure_ascii=False).encode(), "application/json")


def put_raw_routing(store: LocalStorage, ref: TopicRef, data: bytes) -> None:
    store.write("users", routing_path(ref), data, "application/json")


def collect(start: Callable[[], Iterator[Any]]) -> tuple[list[Any], BaseException | None]:
    """Run `start()` and drain it; an exception ends it (NotImplementedError is let through: RED)."""
    items: list[Any] = []
    try:
        for item in start():
            items.append(item)
    except NotImplementedError:
        raise
    except Exception as exc:
        return items, exc
    return items, None


def events(items: Sequence[Any]) -> list[Decision]:
    return [i.decision for i in items if isinstance(i, RoutingEvent)]


def updates(items: Sequence[Any]) -> list[FacilitatorUpdate]:
    return [i for i in items if isinstance(i, FacilitatorUpdate)]


def deltas(items: Sequence[Any]) -> list[ReplyDelta]:
    return [i for i in items if isinstance(i, ReplyDelta)]


def run_converse(
    ctx: FacilitationContext, k: CurrentKnowledge, llm: RouterLlm, lead: RecordingLead
) -> tuple[list[Any], BaseException | None]:
    """`collect` over one `converse` call (imported late: the module is the slice's new code)."""
    from thinkhow.facilitation import converse

    return collect(lambda: converse(ctx, k, llm, lead))
