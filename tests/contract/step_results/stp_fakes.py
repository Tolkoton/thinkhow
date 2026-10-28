"""Helpers for the step-results contract tests (slice tester). Built from the contract, not the code.

- Topics are made through workspace itself (`create_topic`, `reply`, `retry`) with an injected `now`; the
  chosen step lands in map.json through a `MapUpdate` of type `chosen_step` the facilitator double yields.
- Facil: a `Facilitate` double; answers `answer` (with planned map updates and routing decisions), or raises
  `Down` when `answer` is None; records every `FacilitationContext`.
- Rec: a `Recognize` double; records every call `(step, question, text)`; returns its `result` or raises
  `fail`; `on_call` runs inside the call (to look at the stored state at that moment).
- Q: the injected `Question`. Its text holds the step whether it is handed the step (and returns the text)
  or something else (and the `{step}` it returns is filled in): the tests compare the conversation's turn
  with the `step_question` open_topic shows at the same moment, never with a text written here.
- ScenarioLlm: an `Llm` double for `generate_json` that records every call.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from pydantic import BaseModel

from thinkhow.access import CurrentUser
from thinkhow.facilitation.types import (
    Decision,
    FacilitationContext,
    FacilitatorUpdate,
    MapUpdate,
    ReplyDelta,
    RoutingEvent,
    StepOutcome,
)
from thinkhow.platform.config import load_settings
from thinkhow.platform.identity import IapIdentity
from thinkhow.platform.llm import KnowledgeRev, Turn
from thinkhow.platform.speech import ScriptedSpeech
from thinkhow.platform.storage import LocalStorage
from thinkhow.web.server import Deps, create_app
from thinkhow.workspace import (
    NumberedTurn,
    ReplyEvent,
    TopicRef,
    create_topic,
    open_topic,
    reply,
    retry,
    set_language,
)

T0 = datetime(2026, 10, 20, 9, 0, 0, tzinfo=UTC)
S1 = timedelta(seconds=1)
M = timedelta(minutes=1)
H = timedelta(hours=1)
SILENCE = timedelta(hours=24)
DAY = timedelta(hours=25)  # more than the 24 h of silence: the next turn opens a new session

ALICE = CurrentUser(id="alice-1", email="alice@example.com", is_owner=False)
OWNER = CurrentUser(id="owner-9", email="owner@example.com", is_owner=True)

STEP = "Поговорити з трьома клієнтами"
STEP_ID = "s1"

IAP = "x-goog-iap-jwt-assertion"
TOKENS: dict[str, dict[str, str]] = {
    "tok-alice": {"sub": "accounts.google.com:alice-1", "email": "alice@example.com"},
    "tok-owner": {"sub": "accounts.google.com:owner-9", "email": "owner@example.com"},
}
H_ALICE = {IAP: "tok-alice"}
H_OWNER = {IAP: "tok-owner"}

ROOT = Path(__file__).resolve().parents[3]
LOCALES = ROOT / "src" / "thinkhow" / "web" / "locales"

NEW_KEYS = (
    "step_question",
    "steps_title",
    "step_worked",
    "step_not_worked",
    "step_unexpected",
    "step_no_answer",
    "clearer_yes",
    "clearer_partly",
    "clearer_no",
)


def Q(arg: str) -> str:
    """The injected `Question`."""
    return "Минулого разу ви обрали крок «{step}» (" + arg + "). Як він вийшов?"


class Down(Exception):
    """The facilitator's model failed: the person's turn stays without an answer."""


def chosen(step_id: str, text: str, turn: int) -> MapUpdate:
    return MapUpdate(op="add", id=step_id, type="chosen_step", text=text, turn=f"t{turn}")


@dataclass
class Facil:
    answer: str | None = "Добре. Що далі?"
    updates: Sequence[MapUpdate] = ()
    decision: Callable[[FacilitationContext], Decision] | None = None
    contexts: list[FacilitationContext] = field(default_factory=list)

    def __call__(self, context: FacilitationContext) -> Iterator[Any]:
        self.contexts.append(context)
        return self._run(context)

    def _run(self, context: FacilitationContext) -> Iterator[Any]:
        if self.answer is None:
            raise Down("down")
        if self.decision is not None:
            yield RoutingEvent(self.decision(context))
        yield ReplyDelta(text=self.answer)
        yield FacilitatorUpdate(
            reply=self.answer, current_phase_id=None, phase_exit_met=False, map_updates=list(self.updates)
        )


def outcome(
    outcome: str | None = "worked", clearer: str | None = "yes", said: str = "двоє готові платити"
) -> StepOutcome:
    return StepOutcome.model_validate(
        {"answered": True, "outcome": outcome, "clearer": clearer, "said": said}
    )


SKIPPED = StepOutcome(answered=False, outcome=None, clearer=None, said="")


@dataclass
class Rec:
    result: StepOutcome | None = None
    fail: BaseException | None = None
    on_call: Callable[[], None] | None = None
    calls: list[tuple[str, str, str]] = field(default_factory=list)

    def __call__(self, step: str, question: str, text: str) -> StepOutcome | None:
        self.calls.append((step, question, text))
        if self.on_call is not None:
            self.on_call()
        if self.fail is not None:
            raise self.fail
        return self.result


def new_topic(storage: LocalStorage, user: CurrentUser, at: datetime) -> TopicRef:
    return TopicRef(user.id, create_topic(storage, user, "Кав'ярня", at))


def with_chosen_step(
    storage: LocalStorage, at: datetime, step_id: str = STEP_ID, step: str = STEP, user: CurrentUser = ALICE
) -> TopicRef:
    """A topic: the person's turn #1 at `at`, the facilitator's #2 that writes the chosen step (turn t2)."""
    ref = new_topic(storage, user, at - M)
    list(reply(storage, Facil(updates=[chosen(step_id, step, 2)]), user, ref, "Хочу відкрити кав'ярню.", at))
    return ref


def say(
    storage: LocalStorage,
    ref: TopicRef,
    text: str,
    at: datetime,
    facil: Facil | None = None,
    recognize: Rec | None = None,
    user: CurrentUser = ALICE,
) -> list[ReplyEvent]:
    return list(reply(storage, facil or Facil(), user, ref, text, at, recognize=recognize, question=Q))


def again(
    storage: LocalStorage,
    ref: TopicRef,
    at: datetime,
    facil: Facil | None = None,
    recognize: Rec | None = None,
) -> list[ReplyEvent]:
    return list(retry(storage, facil or Facil(), ALICE, ref, at, recognize=recognize))


def turns(storage: LocalStorage, ref: TopicRef, now: datetime) -> list[NumberedTurn]:
    view = open_topic(storage, ALICE, ref, now, question=Q)
    return [t for s in view.sessions for t in s.turns]


def turn_no(storage: LocalStorage, ref: TopicRef, now: datetime, no: int) -> NumberedTurn:
    found = [t for t in turns(storage, ref, now) if t.no == no]
    assert found, f"no turn #{no}: {[(t.no, t.role) for t in turns(storage, ref, now)]}"
    return found[0]


def question_now(storage: LocalStorage, ref: TopicRef, now: datetime) -> str | None:
    return open_topic(storage, ALICE, ref, now, question=Q).step_question


# --- the model -------------------------------------------------------------------------------------


@dataclass
class LlmCall:
    system: str
    contents: list[Turn]
    schema: Any
    rev: KnowledgeRev | None

    @property
    def text(self) -> str:
        return "\n".join(t.text for t in self.contents)

    def lines(self) -> list[str]:
        return [line for line in self.text.split("\n") if line.strip()]


@dataclass
class ScenarioLlm:
    """`answer(schema)` → the value `generate_json` returns, validated by the schema it was given."""

    answer: Callable[[Any], dict[str, Any]]
    calls: list[LlmCall] = field(default_factory=list)

    def stream_json(self, *args: Any, **kwargs: Any) -> Any:
        raise AssertionError("generate_json is the call, not stream_json")

    def search_text(self, *args: Any, **kwargs: Any) -> Any:
        raise AssertionError("generate_json is the call, not search_text")

    def generate_json(
        self, system: str, contents: Sequence[Turn], schema: Any, rev: KnowledgeRev | None
    ) -> Any:
        self.calls.append(LlmCall(system, list(contents), schema, rev))
        return schema.model_validate(self.answer(schema))


def _resolve(schema: dict[str, Any], node: dict[str, Any]) -> dict[str, Any]:
    while "$ref" in node:
        node = schema["$defs"][node["$ref"].rsplit("/", 1)[-1]]
    return node


def anchors_of(schema: type[BaseModel]) -> list[str]:
    js = schema.model_json_schema()
    obs = _resolve(js, js["properties"]["observations"])
    item = _resolve(js, obs["items"])
    return list(_resolve(js, item["properties"]["anchor"])["enum"])


def kinds_of(schema: type[BaseModel]) -> list[str]:
    js = schema.model_json_schema()
    obs = _resolve(js, js["properties"]["observations"])
    item = _resolve(js, obs["items"])
    return list(_resolve(js, item["properties"]["kind"])["enum"])


def one_observation(schema: Any) -> dict[str, Any]:
    anchor = anchors_of(schema)[0]
    return {
        "observations": [
            {"kind": "progress", "finding": "ок", "worked": True, "cause": "method", "anchor": anchor}
        ]
    }


# --- the web ---------------------------------------------------------------------------------------


def make_client(tmp_path: Path, storage: LocalStorage, now: datetime) -> TestClient:
    set_language(storage, ALICE, "uk-UA")
    set_language(storage, OWNER, "uk-UA")
    settings = load_settings(
        {
            "THINKHOW_LOCAL": "true",
            "THINKHOW_LOCAL_DIR": str(tmp_path),
            "THINKHOW_OWNER_EMAIL": "owner@example.com",
        }
    )
    deps = Deps(
        storage=storage,
        identity=IapIdentity("aud-test", lambda token, audience: TOKENS[token]),
        settings=settings,
        facilitate=Facil(),
        now=lambda: now,
        speech=ScriptedSpeech(""),
    )
    return TestClient(create_app(deps), raise_server_exceptions=False, follow_redirects=False)


def page_url(ref: TopicRef) -> str:
    return f"/topics/{ref.uid}/{ref.topic_id}"


def catalog(name: str) -> dict[str, str]:
    data: dict[str, str] = json.loads((LOCALES / f"{name}.json").read_text(encoding="utf-8"))
    return data


def uk(key: str) -> str:
    words = catalog("uk")
    assert key in words, f"no key {key!r} in the uk catalog"
    return words[key]
