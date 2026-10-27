"""Helpers for the analysis-rules contract tests (slice tester). Built from the contract, not the code.

- Topics are made through workspace itself (`create_topic`, `reply`); routing.json is written by
  `workspace.reply` from the `RoutingEvent`s a scenario `Facilitate` yields (Seam 1: «записаним через
  workspace фікстури, а не з мокнутого topic_routing»).
- Knowledge: a real `seed` from a temporary cards folder (titles chosen by the test).
- SetLlm: an `Llm` double for `generate_json`; records every call; answers with the observations a test
  plans (a function of the schema's anchor enum), validated by the schema it was given.
- Observation files: names and JSON under `system/learning/observations/<uid>/<topic>/`.
"""

from __future__ import annotations

import io
import json
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import BaseModel

import thinkhow.platform.log as log
from thinkhow.access import CurrentUser
from thinkhow.facilitation.types import (
    Candidate,
    Decision,
    FacilitationContext,
    FacilitatorUpdate,
    ReplyDelta,
    Rev,
    RoutingEvent,
)
from thinkhow.knowledge import seed
from thinkhow.platform.llm import KnowledgeRev, Turn
from thinkhow.platform.storage import Bucket, LocalStorage
from thinkhow.workspace import TopicRef, create_topic, reply

NOW = datetime(2026, 10, 27, 3, 0, 0, tzinfo=UTC)
H = timedelta(hours=1)
M = timedelta(minutes=1)
DAY = timedelta(hours=25)  # more than 24 h of silence: a new session

ALICE = CurrentUser(id="alice-1", email="alice@example.com", is_owner=False)
BOB = CurrentUser(id="bob_2", email="bob@example.com", is_owner=False)

CTX = "[Контекст — уже проаналізовано, не якір:]"
NEW = "[Нові репліки:]"
REV = Rev(rev=1, n=3)

TITLES = {"alpha": "Альфа", "beta": "Бета", "gamma": "Гамма"}


# --- knowledge -------------------------------------------------------------------------------------


def card_dict(cid: str, title: str) -> dict[str, Any]:
    return {
        "id": cid,
        "title": title,
        "router": {
            "needs": f"роутер-потреба {cid}",
            "when_yes": [f"роутер-так {cid}"],
            "when_no": [f"роутер-ні {cid}"],
            "signals": [f"роутер-сигнал {cid}"],
        },
        "facilitator": {
            "purpose": f"навіщо {cid}",
            "stance": f"позиція {cid}",
            "needs": f"на вході {cid}",
            "phases": [
                {"id": "p_one", "title": "Фаза 1", "goal": "мета 1", "how": ["як 1"], "exit": "вихід 1"},
                {"id": "p_two", "title": "Фаза 2", "goal": "мета 2", "how": ["як 2"], "exit": "вихід 2"},
            ],
            "ending": f"чим закінчується {cid}",
            "traps": [{"name": f"пастка {cid}", "text": f"текст пастки {cid}"}],
            "pairs_well": f"поєднується {cid}",
        },
    }


def seed_cards(storage: LocalStorage, tmp_path: Path, titles: Mapping[str, str] = TITLES) -> None:
    cards_dir = tmp_path / "cards"
    cards_dir.mkdir(parents=True, exist_ok=True)
    for cid, title in titles.items():
        text = yaml.safe_dump(card_dict(cid, title), allow_unicode=True, sort_keys=False)
        (cards_dir / f"{cid}.yaml").write_text(text, encoding="utf-8")
    assert seed(storage, cards_dir)


# --- decisions (as routing.json holds them) --------------------------------------------------------


def d_offer(turn: int, *ids: str) -> Decision:
    return Decision(
        turn=turn,
        rev=REV,
        kind="offer",
        profile=None,
        candidates=[Candidate(card_id=i, why=f"чому {i}") for i in ids],
        card_id=None,
        end=None,
        why="пропоную",
    )


def d_ask(turn: int) -> Decision:
    return Decision(
        turn=turn, rev=REV, kind="ask", profile=None, candidates=[], card_id=None, end=None, why="питаю"
    )


def d_answer(turn: int) -> Decision:
    return Decision(
        turn=turn, rev=REV, kind="answer", profile=None, candidates=[], card_id=None, end=None, why="факт"
    )


def d_choose(turn: int, cid: str) -> Decision:
    return Decision(
        turn=turn, rev=REV, kind="choose", profile=None, candidates=[], card_id=cid, end=None, why="обрано"
    )


def d_end(turn: int, cid: str, end: str) -> Decision:
    return Decision.model_validate(
        {
            "turn": turn,
            "rev": REV.model_dump(),
            "kind": "end",
            "profile": None,
            "candidates": [],
            "card_id": cid,
            "end": end,
            "why": "кінець",
        }
    )


# --- topics ----------------------------------------------------------------------------------------


@dataclass
class Scripted:
    """A `Facilitate` that answers `answer` after yielding the planned `RoutingEvent`s."""

    answer: str
    decisions: Sequence[Decision] = ()

    def __call__(self, context: FacilitationContext) -> Iterator[Any]:
        return self._run()

    def _run(self) -> Iterator[Any]:
        for d in self.decisions:
            yield RoutingEvent(d)
        yield ReplyDelta(text=self.answer)
        yield FacilitatorUpdate(
            reply=self.answer, current_phase_id="p1", phase_exit_met=False, map_updates=[]
        )


def new_topic(storage: LocalStorage, user: CurrentUser, at: datetime, title: str = "Тема") -> TopicRef:
    return TopicRef(user.id, create_topic(storage, user, title, at))


def say(
    storage: LocalStorage,
    user: CurrentUser,
    ref: TopicRef,
    text: str,
    answer: str,
    at: datetime,
    decisions: Sequence[Decision] = (),
) -> None:
    """The person's turn and the facilitator's answer (two turns), with the router's decisions."""
    list(reply(storage, Scripted(answer, decisions), user, ref, text, at))


def talk(
    storage: LocalStorage,
    user: CurrentUser,
    ref: TopicRef,
    pairs: int,
    start: datetime,
    by_turn: Mapping[int, Sequence[Decision]] | None = None,
    first_no: int = 1,
) -> None:
    """`pairs` exchanges numbered from `first_no`: person `n` («людина n»), facilitator `n + 1`; the
    decisions of `by_turn[n]` come with the person's turn `n`. One minute apart (one session)."""
    plan = by_turn or {}
    for i in range(pairs):
        n = first_no + 2 * i
        say(storage, user, ref, f"людина {n}", f"фасилітатор {n + 1}", start + i * M, plan.get(n, ()))


def routing_path(ref: TopicRef) -> str:
    return f"{ref.uid}/{ref.topic_id}/routing.json"


# --- observations ----------------------------------------------------------------------------------


def obs_dir(uid: str, topic_id: str) -> str:
    return f"learning/observations/{uid}/{topic_id}/"


def obs_names(storage: LocalStorage, ref: TopicRef) -> set[str]:
    return {p.rsplit("/", 1)[-1] for p in storage.list("system", obs_dir(ref.uid, ref.topic_id))}


def obs(storage: LocalStorage, ref: TopicRef, name: str) -> dict[str, Any]:
    raw = storage.read("system", obs_dir(ref.uid, ref.topic_id) + name)
    assert raw is not None, f"no observation file {name}"
    data = json.loads(raw)
    assert isinstance(data, dict)
    return data


def put_raw(storage: LocalStorage, uid: str, topic_id: str, name: str, body: str | bytes) -> None:
    data = body.encode("utf-8") if isinstance(body, str) else body
    storage.write("system", obs_dir(uid, topic_id) + name, data, "application/json")


# --- the model -------------------------------------------------------------------------------------


def _resolve(schema: dict[str, Any], node: dict[str, Any]) -> dict[str, Any]:
    while "$ref" in node:
        name = node["$ref"].rsplit("/", 1)[-1]
        node = schema["$defs"][name]
    return node


def item_schema(schema: type[BaseModel]) -> dict[str, Any]:
    """The JSON schema of one observation of the answer (the `items` of `observations`)."""
    js = schema.model_json_schema()
    assert "observations" in js["properties"], f"no observations in the schema: {list(js['properties'])}"
    obs_prop = _resolve(js, js["properties"]["observations"])
    return _resolve(js, obs_prop["items"])


def observations_prop(schema: type[BaseModel]) -> dict[str, Any]:
    js = schema.model_json_schema()
    assert "observations" in js["properties"], f"no observations in the schema: {list(js['properties'])}"
    return _resolve(js, js["properties"]["observations"])


def anchors_of(schema: type[BaseModel]) -> list[str]:
    js = schema.model_json_schema()
    prop = _resolve(js, item_schema(schema)["properties"]["anchor"])
    return list(prop["enum"])


def one(
    anchor: str, kind: str = "stuck", cause: str = "facilitation", worked: bool = False
) -> dict[str, Any]:
    return {
        "kind": kind,
        "finding": f"спостереження на {anchor}",
        "worked": worked,
        "cause": cause,
        "anchor": anchor,
    }


Plan = Callable[[list[str]], list[dict[str, Any]]]


def at_first(anchors: list[str]) -> list[dict[str, Any]]:
    return [one(anchors[0], kind="progress", cause="method", worked=True)]


@dataclass
class LlmCall:
    system: str
    contents: list[Turn]
    schema: type[BaseModel]
    rev: KnowledgeRev | None

    @property
    def text(self) -> str:
        return "\n".join(t.text for t in self.contents)

    def lines(self) -> list[str]:
        """The non-empty lines of the text (blank lines between blocks are not part of the contract)."""
        return [line for line in self.text.split("\n") if line.strip()]

    def anchors(self) -> list[str]:
        return anchors_of(self.schema)


@dataclass
class SetLlm:
    """`plan(anchors)` → the observations of the answer; `fail_all`: every call raises it."""

    plan: Plan = at_first
    fail_all: BaseException | None = None
    calls: list[LlmCall] = field(default_factory=list)

    def stream_json(self, *args: Any, **kwargs: Any) -> Any:
        raise AssertionError("the analyzer must use generate_json, not stream_json")

    def generate_json(
        self, system: str, contents: Sequence[Turn], schema: Any, rev: KnowledgeRev | None
    ) -> Any:
        call = LlmCall(system, list(contents), schema, rev)
        self.calls.append(call)
        if self.fail_all is not None:
            raise self.fail_all
        return schema.model_validate({"observations": self.plan(anchors_of(schema))})


# --- writes and logs -------------------------------------------------------------------------------


@dataclass
class WriteRec:
    bucket: Bucket
    path: str


class SpyStorage(LocalStorage):
    def __init__(self, root: Path) -> None:
        super().__init__(root)
        self.writes: list[WriteRec] = []
        self.recording = False

    def write(self, bucket: Bucket, path: str, data: bytes, content_type: str) -> None:
        if self.recording:
            self.writes.append(WriteRec(bucket, path))
        super().write(bucket, path, data, content_type)

    def create_if_absent(self, bucket: Bucket, path: str, data: bytes, content_type: str) -> bool:
        if self.recording:
            self.writes.append(WriteRec(bucket, path))
        return super().create_if_absent(bucket, path, data, content_type)


class LogCapture:
    def __init__(self) -> None:
        self.buffer = io.StringIO()

    def events(self, name: str) -> list[dict[str, Any]]:
        found = []
        for line in self.buffer.getvalue().splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            obj = json.loads(line)
            if isinstance(obj, dict) and obj.get("event") == name:
                found.append(obj)
        return found

    def text(self) -> str:
        return self.buffer.getvalue()


def install_log_capture(monkeypatch: pytest.MonkeyPatch) -> LogCapture:
    cap = LogCapture()
    monkeypatch.setattr(log.log_event, "__defaults__", (cap.buffer,))
    return cap
