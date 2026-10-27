"""Helpers for the synthesizer contract tests (slice tester). Built from the contract, not the code.

- Knowledge: a real `seed` from a temporary cards folder (alpha, beta, gamma, each with a method and phases
  whose words are unique, so a test can tell that no phase reached the model's text).
- Observations: hand-written set files `learning/observations/<uid>/<topic>/t<a>-t<b>.json` (the S2 shape the
  one reader `read_all` reads), with ids and links chosen by the test.
- SynthLlm: an `Llm` double for `generate_json`; records every call; answers with the next planned answer
  (a dict validated by the schema it was given — the way the scripted model of local mode does) or raises the
  planned exception.
- SpyStorage: a `LocalStorage` that records reads and writes and can force `create_if_absent` under a prefix.
- Run records: the files under `system/learning/synthesis/`.
- make_client: the web app over the same storage, with an owner and a person who is not the owner.
"""

from __future__ import annotations

import io
import json
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

import pytest
import yaml
from fastapi.testclient import TestClient
from pydantic import BaseModel

import thinkhow.platform.log as log
from thinkhow.access import CurrentUser
from thinkhow.facilitation.types import FacilitationContext, FacilitatorUpdate, ReplyDelta
from thinkhow.knowledge import (
    ChangeRecord,
    CurrentKnowledge,
    MemoryChange,
    MemoryRecord,
    apply_memory,
    current,
    seed,
)
from thinkhow.platform.config import load_settings
from thinkhow.platform.identity import IapIdentity
from thinkhow.platform.llm import KnowledgeRev, Turn
from thinkhow.platform.speech import ScriptedSpeech
from thinkhow.platform.storage import Bucket, LocalStorage
from thinkhow.web.server import Deps, create_app
from thinkhow.workspace import set_language

NOW = datetime(2026, 10, 27, 12, 0, 0, tzinfo=UTC)
H = timedelta(hours=1)
DAY = timedelta(days=1)
RUNS = "learning/synthesis/"
CHANGES = "knowledge/changes/"
CARDS_PREFIX = "knowledge/cards/"
ROLLBACKS = "knowledge/rollbacks/"
HEADER = "Відкочено власником — не пропонуй знову"

TITLES = {"alpha": "Альфа", "beta": "Бета", "gamma": "Гамма"}


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
                },
                {
                    "id": "p_two",
                    "title": f"фазаназва-{cid}-2",
                    "goal": f"фазамета-{cid}-2",
                    "how": [f"фазахід-{cid}-2"],
                    "exit": f"фазавихід-{cid}-2",
                },
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
        self.reads: list[tuple[Bucket, str]] = []
        self.writes: list[tuple[Bucket, str]] = []
        self.lists: list[tuple[Bucket, str]] = []
        self.forced: tuple[str, bool] | None = None

    def read(self, bucket: Bucket, path: str) -> bytes | None:
        self.reads.append((bucket, path))
        return super().read(bucket, path)

    def list(self, bucket: Bucket, prefix: str) -> list[str]:
        self.lists.append((bucket, prefix))
        return super().list(bucket, prefix)

    def write(self, bucket: Bucket, path: str, data: bytes, content_type: str) -> None:
        self.writes.append((bucket, path))
        super().write(bucket, path, data, content_type)

    def create_if_absent(self, bucket: Bucket, path: str, data: bytes, content_type: str) -> bool:
        self.writes.append((bucket, path))
        if self.forced is not None and path.startswith(self.forced[0]):
            return self.forced[1]
        return super().create_if_absent(bucket, path, data, content_type)

    def reset(self) -> None:
        self.reads.clear()
        self.writes.clear()
        self.lists.clear()


def seeded(tmp_path: Path) -> SpyStorage:
    """Revision 1: the real `seed` of alpha, beta, gamma (no memory)."""
    storage = SpyStorage(tmp_path / "bucket")
    assert seed(storage, write_cards(tmp_path / "cards"))
    assert current(storage).rev == 1
    return storage


def note(
    mid: str,
    cards: Sequence[str] = ("alpha",),
    basis: str = "стартове джерело",
    audience: Literal["router", "facilitator"] = "facilitator",
    noticed: str | None = None,
    do: str | None = None,
) -> MemoryRecord:
    return MemoryRecord(
        id=mid,
        title=f"заголовок {mid}",
        cards=list(cards),
        noticed=noticed if noticed is not None else f"помічено {mid}",
        do=do if do is not None else f"робити {mid}",
        basis=basis,
        audience=audience,
    )


def ok_vet(records: Sequence[MemoryRecord]) -> str | None:
    return None


def zero_measure(knowledge: CurrentKnowledge) -> int:
    return 0


def hand_apply(
    storage: LocalStorage,
    upsert: Sequence[MemoryRecord] = (),
    remove: Sequence[str] = (),
    observations: Sequence[str] = (),
    what: str = "зміна руками",
) -> int:
    change = MemoryChange(
        what=what,
        why="чому руками",
        by="owner-test",
        upsert=list(upsert),
        remove=list(remove),
        observations=list(observations),
    )
    rev = apply_memory(storage, change, ok_vet, zero_measure)
    assert isinstance(rev, int)
    return rev


def memory(storage: LocalStorage) -> dict[str, MemoryRecord]:
    return {r.id: r for r in current(storage).memory}


def change_record(storage: LocalStorage, rev: int | None) -> ChangeRecord:
    assert rev is not None
    raw = LocalStorage.read(storage, "system", f"{CHANGES}{rev:06d}.json")
    assert raw is not None, rev
    return ChangeRecord.model_validate_json(raw)


def change_files(storage: LocalStorage) -> list[str]:
    return sorted(LocalStorage.list(storage, "system", CHANGES))


def snapshot(storage: LocalStorage, prefix: str) -> dict[str, bytes]:
    return {
        p: LocalStorage.read(storage, "system", p) or b""
        for p in sorted(LocalStorage.list(storage, "system", prefix))
    }


# --- observations ----------------------------------------------------------------------------------


@dataclass(frozen=True)
class Ob:
    """One observation as the test plans it; `id` and `link` are what the set file holds."""

    uid: str
    topic: str
    first: int
    last: int
    k: int
    turn: int
    finding: str
    kind: str = "stuck"
    cause: str = "facilitation"
    card_id: str | None = "alpha"
    worked: bool = False
    analyzed_at: datetime = NOW - 2 * H

    @property
    def id(self) -> str:
        return f"{self.uid}/{self.topic}/t{self.first}-t{self.last}/{self.k}"

    @property
    def link(self) -> str:
        return f"/topics/{self.uid}/{self.topic}#t{self.turn}"


def put_set(storage: LocalStorage, items: Sequence[Ob]) -> list[Ob]:
    """One set file holding `items` (all of one uid, topic, range)."""
    first = items[0]
    data = {
        "uid": first.uid,
        "topic_id": first.topic,
        "first_turn": first.first,
        "last_turn": first.last,
        "analyzed_at": first.analyzed_at.isoformat(),
        "observations": [
            {
                "id": o.id,
                "turn": o.turn,
                "link": o.link,
                "kind": o.kind,
                "worked": o.worked,
                "finding": o.finding,
                "cause": o.cause,
                "card_id": o.card_id,
                "analyzed_at": o.analyzed_at.isoformat(),
            }
            for o in items
        ],
    }
    path = f"learning/observations/{first.uid}/{first.topic}/t{first.first}-t{first.last}.json"
    LocalStorage.write(
        storage, "system", path, json.dumps(data, ensure_ascii=False).encode(), "application/json"
    )
    return list(items)


def one_obs(storage: LocalStorage, topic: str, first: int, finding: str, **extra: Any) -> Ob:
    """A set file `t<first>-t<first+1>` with one observation on turn `first`."""
    o = Ob(
        uid=extra.pop("uid", "u-a"),
        topic=topic,
        first=first,
        last=first + 1,
        k=1,
        turn=first,
        finding=finding,
        **extra,
    )
    put_set(storage, [o])
    return o


# --- the model -------------------------------------------------------------------------------------


def upsert_item(
    mid: str,
    observations: Sequence[str],
    cards: Sequence[str] = ("alpha",),
    audience: str = "facilitator",
    title: str | None = None,
    noticed: str | None = None,
    do: str | None = None,
) -> dict[str, Any]:
    return {
        "id": mid,
        "audience": audience,
        "cards": list(cards),
        "title": title if title is not None else f"нова назва {mid}",
        "noticed": noticed if noticed is not None else f"нове помічено {mid}",
        "do": do if do is not None else f"нове робити {mid}",
        "observations": list(observations),
    }


def remove_item(mid: str, observations: Sequence[str]) -> dict[str, Any]:
    return {"id": mid, "observations": list(observations)}


def answer(
    upsert: Sequence[dict[str, Any]] = (),
    remove: Sequence[dict[str, Any]] = (),
    what: str = "що змінено синтезатором",
    why: str = "чому змінено синтезатором",
) -> dict[str, Any]:
    return {"what": what, "why": why, "upsert": list(upsert), "remove": list(remove)}


@dataclass
class LlmCall:
    system: str
    contents: list[Turn]
    schema: type[BaseModel]
    rev: KnowledgeRev | None

    @property
    def text(self) -> str:
        return "\n".join(t.text for t in self.contents)


@dataclass
class SynthLlm:
    """`plan`: one item a call — a dict (validated by the call's schema) or an exception to raise.
    After the plan is used up every call answers `default` (no change)."""

    plan: list[Any] = field(default_factory=list)
    default: dict[str, Any] = field(default_factory=lambda: answer())
    calls: list[LlmCall] = field(default_factory=list)

    def stream_json(self, *args: Any, **kwargs: Any) -> Any:
        raise AssertionError("the synthesizer must use generate_json, not stream_json")

    def search_text(self, *args: Any, **kwargs: Any) -> Any:
        raise AssertionError("the synthesizer must use generate_json, not search_text")

    def generate_json(
        self, system: str, contents: Sequence[Turn], schema: Any, rev: KnowledgeRev | None
    ) -> Any:
        self.calls.append(LlmCall(system, list(contents), schema, rev))
        item = self.plan.pop(0) if self.plan else self.default
        if isinstance(item, BaseException):
            raise item
        return schema.model_validate(item)


# --- run records -----------------------------------------------------------------------------------


def run_files(storage: LocalStorage) -> list[str]:
    return sorted(LocalStorage.list(storage, "system", RUNS))


def run_record(storage: LocalStorage, path: str) -> dict[str, Any]:
    raw = LocalStorage.read(storage, "system", path)
    assert raw is not None, path
    data = json.loads(raw)
    assert isinstance(data, dict)
    return data


def all_run_records(storage: LocalStorage) -> list[dict[str, Any]]:
    return [run_record(storage, p) for p in run_files(storage)]


# --- logs ------------------------------------------------------------------------------------------


class LogCapture:
    def __init__(self, capsys: Any) -> None:
        self.buffer = io.StringIO()
        self.capsys = capsys
        self._out = ""

    def lines(self) -> list[dict[str, Any]]:
        got = self.capsys.readouterr()
        self._out += got.out + "\n" + got.err
        found: list[dict[str, Any]] = []
        for line in (self.buffer.getvalue() + "\n" + self._out).splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            if isinstance(obj, dict):
                found.append(obj)
        return found

    def events(self, name: str) -> list[dict[str, Any]]:
        return [line for line in self.lines() if line.get("event") == name]


def install_log_capture(monkeypatch: pytest.MonkeyPatch, capsys: Any) -> LogCapture:
    cap = LogCapture(capsys)
    monkeypatch.setattr(log.log_event, "__defaults__", (cap.buffer,))
    return cap


# --- the web app -----------------------------------------------------------------------------------

IAP = "x-goog-iap-jwt-assertion"
OWNER = CurrentUser(id="owner-1", email="owner@example.com", is_owner=True)
ALICE = CurrentUser(id="alice-1", email="alice@example.com", is_owner=False)
TOKENS: dict[str, dict[str, str]] = {
    "tok-owner": {"sub": "accounts.google.com:owner-1", "email": "owner@example.com"},
    "tok-alice": {"sub": "accounts.google.com:alice-1", "email": "alice@example.com"},
}
H_OWNER = {IAP: "tok-owner"}
H_ALICE = {IAP: "tok-alice"}


def _verify(token: str, audience: str) -> Mapping[str, object]:
    if token not in TOKENS:
        raise RuntimeError("bad signature")
    return TOKENS[token]


@dataclass
class OneAnswer:
    answer: str = "Так?"

    def __call__(self, context: FacilitationContext) -> Iterator[ReplyDelta | FacilitatorUpdate]:
        yield ReplyDelta(text=self.answer)
        yield FacilitatorUpdate(
            reply=self.answer, current_phase_id="p1", phase_exit_met=False, map_updates=[]
        )


def make_client(tmp_path: Path, storage: LocalStorage) -> TestClient:
    set_language(storage, OWNER, "uk-UA")
    set_language(storage, ALICE, "uk-UA")
    settings = load_settings(
        {
            "THINKHOW_LOCAL": "true",
            "THINKHOW_LOCAL_DIR": str(tmp_path / "local"),
            "THINKHOW_OWNER_EMAIL": "owner@example.com",
        }
    )
    deps = Deps(
        storage=storage,
        identity=IapIdentity("aud-test", _verify),
        settings=settings,
        facilitate=OneAnswer(),
        now=lambda: NOW + H,
        speech=ScriptedSpeech("(локальний режим) розпізнаний текст"),
    )
    return TestClient(create_app(deps), raise_server_exceptions=False, follow_redirects=False)
