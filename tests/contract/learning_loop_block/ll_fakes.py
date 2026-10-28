"""Helpers for the block tests of learning-loop (slice tester, mode `block`). Built from the feature
artifact `.engine/architecture/feature/learning-loop.md`, the slice contracts it names and the public
signatures — not the bodies.

- Cards: a temporary folder alpha, beta, gamma (words of every phase unique), or the real `cards/` (25).
- Topics go through `workspace` itself (`create_topic`, `reply`) with an injected `now`; the chosen
  step lands in map.json through a `MapUpdate` of type `chosen_step` the facilitator double yields.
- ScenarioLlm: an `Llm` double for `generate_json`; `answer(schema)` gives the value (validated by the
  schema it was handed); records every call.
- SpyStorage: a `LocalStorage` that records every write.
- make_client: the web app over a storage, with the owner and a person who is not the owner.
"""

from __future__ import annotations

import html
import json
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml
from fastapi.testclient import TestClient
from pydantic import BaseModel

from thinkhow.access import CurrentUser
from thinkhow.facilitation.types import (
    FacilitationContext,
    FacilitatorUpdate,
    MapUpdate,
    ReplyDelta,
    StepOutcome,
)
from thinkhow.knowledge import CurrentKnowledge, MemoryRecord, current, seed
from thinkhow.platform.config import load_settings
from thinkhow.platform.identity import IapIdentity
from thinkhow.platform.llm import KnowledgeRev, Turn
from thinkhow.platform.speech import ScriptedSpeech
from thinkhow.platform.storage import Bucket, LocalStorage
from thinkhow.web.server import Deps, create_app
from thinkhow.workspace import Recognize, TopicRef, create_topic, reply, set_language

ROOT = Path(__file__).resolve().parents[3]
CARDS = ROOT / "cards"
NOTES = ROOT / "notes"
ARTIFACTS = ROOT / ".engine" / "artifacts"
LOCALES = ROOT / "src" / "thinkhow" / "web" / "locales"

T0 = datetime(2026, 10, 20, 9, 0, 0, tzinfo=UTC)
M = timedelta(minutes=1)
H = timedelta(hours=1)
DAY = timedelta(hours=25)  # more than the 24 h of silence: the next turn opens a new session

ALICE = CurrentUser(id="alice-1", email="alice@example.com", is_owner=False)
OWNER = CurrentUser(id="owner-9", email="owner@example.com", is_owner=True)

IAP = "x-goog-iap-jwt-assertion"
TOKENS: dict[str, dict[str, str]] = {
    "tok-alice": {"sub": "accounts.google.com:alice-1", "email": "alice@example.com"},
    "tok-owner": {"sub": "accounts.google.com:owner-9", "email": "owner@example.com"},
}
H_ALICE = {IAP: "tok-alice"}
H_OWNER = {IAP: "tok-owner"}

STEP = "Поговорити з трьома клієнтами"
STEP_ID = "s1"
HEADER = "Відкочено власником — не пропонуй знову"
TITLES = {"alpha": "Альфа", "beta": "Бета", "gamma": "Гамма"}


def local_environ(root: Path) -> dict[str, str]:
    return {
        "THINKHOW_LOCAL": "true",
        "THINKHOW_LOCAL_DIR": str(root),
        "THINKHOW_OWNER_EMAIL": "owner@example.com",
    }


# --- knowledge -------------------------------------------------------------------------------------


def card_dict(cid: str, title: str) -> dict[str, Any]:
    return {
        "id": cid,
        "title": title,
        "method": f"Метод-{cid}",
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
                {
                    "id": "p_one",
                    "title": f"фазаназва-{cid}-1",
                    "goal": f"фазамета-{cid}-1",
                    "how": [f"фазахід-{cid}-1"],
                    "exit": f"фазавихід-{cid}-1",
                }
            ],
            "ending": f"чим закінчується {cid}",
            "traps": [{"name": f"пастка {cid}", "text": f"текст пастки {cid}"}],
            "pairs_well": f"поєднується {cid}",
        },
    }


def write_cards(cards_dir: Path, titles: Mapping[str, str] = TITLES) -> Path:
    cards_dir.mkdir(parents=True, exist_ok=True)
    for cid, title in titles.items():
        text = yaml.safe_dump(card_dict(cid, title), allow_unicode=True, sort_keys=False)
        (cards_dir / f"{cid}.yaml").write_text(text, encoding="utf-8")
    return cards_dir


class SpyStorage(LocalStorage):
    def __init__(self, root: Path) -> None:
        super().__init__(root)
        self.writes: list[tuple[Bucket, str]] = []

    def write(self, bucket: Bucket, path: str, data: bytes, content_type: str) -> None:
        self.writes.append((bucket, path))
        super().write(bucket, path, data, content_type)

    def create_if_absent(self, bucket: Bucket, path: str, data: bytes, content_type: str) -> bool:
        self.writes.append((bucket, path))
        return super().create_if_absent(bucket, path, data, content_type)


def seeded(tmp_path: Path, cards_dir: Path | None = None) -> SpyStorage:
    """Revision 1: the real `seed` (no memory)."""
    storage = SpyStorage(tmp_path / "bucket")
    assert seed(storage, cards_dir or write_cards(tmp_path / "cards"))
    assert current(storage).rev == 1
    return storage


def system_json(storage: LocalStorage, path: str) -> dict[str, Any]:
    raw = LocalStorage.read(storage, "system", path)
    assert raw is not None, path
    data = json.loads(raw)
    assert isinstance(data, dict)
    return data


def system_files(storage: LocalStorage, prefix: str) -> list[str]:
    return sorted(LocalStorage.list(storage, "system", prefix))


def snapshot(storage: LocalStorage, prefix: str) -> dict[str, bytes]:
    return {p: LocalStorage.read(storage, "system", p) or b"" for p in system_files(storage, prefix)}


def memory_of(storage: LocalStorage) -> dict[str, MemoryRecord]:
    return {r.id: r for r in current(storage).memory}


def ok_vet(records: Sequence[MemoryRecord]) -> str | None:
    return None


def zero_measure(knowledge: CurrentKnowledge) -> int:
    return 0


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


def analyzer_says(kind: str = "stuck", anchor: str | None = None, finding: str = "людина застрягла") -> Any:
    """The analyzer's answer: one observation, anchored to `anchor` (or the first new turn)."""

    def answer(schema: Any) -> dict[str, Any]:
        where = anchor if anchor is not None else anchors_of(schema)[0]
        return {
            "observations": [
                {"kind": kind, "finding": finding, "worked": False, "cause": "facilitation", "anchor": where}
            ]
        }

    return answer


def upsert_item(
    mid: str,
    observations: Sequence[str] = ("o1",),
    cards: Sequence[str] = ("alpha",),
    audience: str = "facilitator",
    noticed: str | None = None,
    do: str | None = None,
) -> dict[str, Any]:
    return {
        "id": mid,
        "audience": audience,
        "cards": list(cards),
        "title": f"назва {mid}",
        "noticed": noticed if noticed is not None else f"помічено {mid}",
        "do": do if do is not None else f"робити {mid}",
        "observations": list(observations),
    }


def synth_says(*upsert: dict[str, Any], remove: Sequence[dict[str, Any]] = ()) -> Any:
    def answer(schema: Any) -> dict[str, Any]:
        return {"what": "що змінено", "why": "чому змінено", "upsert": list(upsert), "remove": list(remove)}

    return answer


# --- observations written by hand (old shapes: literal JSON of the old models) ---------------------------


def put_raw(storage: LocalStorage, uid: str, topic: str, name: str, text: str) -> None:
    path = f"learning/observations/{uid}/{topic}/{name}"
    LocalStorage.write(storage, "system", path, text.encode("utf-8"), "application/json")


# --- topics ----------------------------------------------------------------------------------------


def Q(arg: str) -> str:
    """The injected `Question`."""
    return "Минулого разу ви обрали крок «{step}» (" + arg + "). Як він вийшов?"


def chosen(step_id: str, text: str, turn: int) -> MapUpdate:
    return MapUpdate(op="add", id=step_id, type="chosen_step", text=text, turn=f"t{turn}")


@dataclass
class Facil:
    answer: str = "Добре. Що далі?"
    updates: Sequence[MapUpdate] = ()
    contexts: list[FacilitationContext] = field(default_factory=list)

    def __call__(self, context: FacilitationContext) -> Iterator[Any]:
        self.contexts.append(context)
        return self._run()

    def _run(self) -> Iterator[Any]:
        yield ReplyDelta(text=self.answer)
        yield FacilitatorUpdate(
            reply=self.answer, current_phase_id=None, phase_exit_met=False, map_updates=list(self.updates)
        )


def outcome(
    result: str | None = "worked", clearer: str | None = "yes", said: str = "двоє готові платити"
) -> StepOutcome:
    return StepOutcome.model_validate({"answered": True, "outcome": result, "clearer": clearer, "said": said})


SKIPPED = StepOutcome(answered=False, outcome=None, clearer=None, said="")


@dataclass
class Rec:
    result: StepOutcome | None = None
    calls: list[tuple[str, str, str]] = field(default_factory=list)

    def __call__(self, step: str, question: str, text: str) -> StepOutcome | None:
        self.calls.append((step, question, text))
        return self.result


def with_chosen_step(
    storage: LocalStorage, at: datetime, step_id: str = STEP_ID, step: str = STEP, user: CurrentUser = ALICE
) -> TopicRef:
    """A topic: the person's turn #1 at `at`, the facilitator's #2 that writes the chosen step (turn t2)."""
    ref = TopicRef(user.id, create_topic(storage, user, "Кав'ярня", at - M))
    list(reply(storage, Facil(updates=[chosen(step_id, step, 2)]), user, ref, "Хочу відкрити кав'ярню.", at))
    return ref


def say(
    storage: LocalStorage,
    ref: TopicRef,
    text: str,
    at: datetime,
    recognize: Recognize | None = None,
    user: CurrentUser = ALICE,
) -> None:
    list(reply(storage, Facil(), user, ref, text, at, recognize=recognize, question=Q))


# --- the web ---------------------------------------------------------------------------------------


@dataclass
class Clock:
    now: datetime

    def __call__(self) -> datetime:
        return self.now


def make_client(
    tmp_path: Path, storage: LocalStorage, clock: Clock, recognize: Recognize | None = None
) -> TestClient:
    set_language(storage, ALICE, "uk-UA")
    set_language(storage, OWNER, "uk-UA")
    settings = load_settings(local_environ(tmp_path / "local"))
    deps = Deps(
        storage=storage,
        identity=IapIdentity("aud-test", lambda token, audience: TOKENS[token]),
        settings=settings,
        facilitate=Facil(),
        now=clock,
        speech=ScriptedSpeech(""),
        recognize=recognize,
    )
    return TestClient(create_app(deps), raise_server_exceptions=False, follow_redirects=False)


def page(client: TestClient, url: str, headers: dict[str, str]) -> str:
    r = client.get(url, headers=headers)
    assert r.status_code == 200, r.text[:300]
    return html.unescape(r.text)


def topic_url(ref: TopicRef) -> str:
    return f"/topics/{ref.uid}/{ref.topic_id}"


def uk(key: str) -> str:
    words: dict[str, str] = json.loads((LOCALES / "uk.json").read_text(encoding="utf-8"))
    assert key in words, f"no key {key!r} in the uk catalog"
    return words[key]
