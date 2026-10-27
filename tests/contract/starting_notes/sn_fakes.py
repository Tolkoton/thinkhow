"""Helpers for the starting-notes contract tests (slice tester). Built from the contract, not the code.

- write_cards: a temporary `cards/` of alpha, beta, gamma (the card shape of the earlier slices' tests).
- note_dict / write_notes: `notes/<card-id>.yaml` files, each a YAML list of MemoryRecord dicts.
- Job: the Job's `run` in local mode on a temporary folder; `notes/` beside `cards/`, `NOTES_DIR` at it.
- VetLlm: a model port for `generate_json` that answers the vet (or raises), and records every call.
- hand_change: `apply_memory` by another writer (the synthesizer, the owner) with a passing vet.
- Reading the bucket: change files, the newest change record, a snapshot of a prefix, the current memory.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import BaseModel

import thinkhow.learning.job as job
from thinkhow.knowledge import (
    ChangeRecord,
    CurrentKnowledge,
    MemoryChange,
    MemoryRecord,
    apply_memory,
    current,
)
from thinkhow.platform.llm import KnowledgeRev, Turn
from thinkhow.platform.storage import LocalStorage

NOW = datetime(2026, 10, 27, 12, 0, 0, tzinfo=UTC)
CHANGES = "knowledge/changes/"
CARDS_PREFIX = "knowledge/cards/"
WHY = "дослідження типових випадків застосування (задача 309)"
WHAT = "стартові нотатки до методів: "

TITLES = {"alpha": "Альфа", "beta": "Бета", "gamma": "Гамма"}


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
                {"id": "p_one", "title": "Фаза 1", "goal": "мета 1", "how": ["як 1"], "exit": "вихід 1"},
                {"id": "p_two", "title": "Фаза 2", "goal": "мета 2", "how": ["як 2"], "exit": "вихід 2"},
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


def note_dict(
    mid: str,
    cards: Sequence[str],
    audience: str,
    noticed: str | None = None,
    basis: str = "Автор А., «Назва», 2001 — https://example.org/a — відкрито",
) -> dict[str, Any]:
    return {
        "id": mid,
        "audience": audience,
        "cards": list(cards),
        "title": f"заголовок {mid}",
        "noticed": noticed if noticed is not None else f"помічено {mid}",
        "do": f"робити {mid}",
        "basis": basis,
    }


def router(cid: str, *extra_cards: str, noticed: str | None = None) -> dict[str, Any]:
    return note_dict(f"{cid}-router", [cid, *extra_cards], "router", noticed)


def facilitator(cid: str, noticed: str | None = None) -> dict[str, Any]:
    return note_dict(f"{cid}-facilitator", [cid], "facilitator", noticed)


def write_file(notes_dir: Path, name: str, items: Any) -> Path:
    notes_dir.mkdir(parents=True, exist_ok=True)
    path = notes_dir / name
    path.write_text(yaml.safe_dump(items, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return path


def as_record(item: Mapping[str, Any]) -> MemoryRecord:
    return MemoryRecord.model_validate(dict(item))


@dataclass
class VetCall:
    system: str
    contents: list[Turn]
    schema: type[BaseModel]


@dataclass
class VetLlm:
    """Answers every `generate_json` with `{ok, reason}` validated by the call's schema, or raises `error`."""

    ok: bool = True
    reason: str = ""
    error: BaseException | None = None
    calls: list[VetCall] = field(default_factory=list)
    streamed: int = 0

    def stream_json(self, *args: Any, **kwargs: Any) -> Any:
        self.streamed += 1
        raise AssertionError("`notes` calls no model but the vet's generate_json")

    def search_text(self, *args: Any, **kwargs: Any) -> Any:
        raise AssertionError("`notes` calls no model but the vet's generate_json")

    def generate_json(
        self, system: str, contents: Sequence[Turn], schema: Any, rev: KnowledgeRev | None
    ) -> Any:
        self.calls.append(VetCall(system, list(contents), schema))
        if self.error is not None:
            raise self.error
        return schema.model_validate({"ok": self.ok, "reason": self.reason})


class Job:
    """The Job on `tmp/local` (local mode), cards in `tmp/cards`, notes in `tmp/notes` (beside the cards)."""

    def __init__(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self.root = tmp_path / "local"
        self.cards = write_cards(tmp_path / "cards")
        self.notes = tmp_path / "notes"
        self.notes.mkdir(parents=True, exist_ok=True)
        self.monkeypatch = monkeypatch
        monkeypatch.setattr(job, "NOTES_DIR", self.notes)
        self.storage = LocalStorage(self.root)

    @property
    def environ(self) -> dict[str, str]:
        return {
            "THINKHOW_LOCAL": "true",
            "THINKHOW_LOCAL_DIR": str(self.root),
            "THINKHOW_OWNER_EMAIL": "owner@localhost",
        }

    def __call__(self, command: str) -> int:
        return job.run([command], self.environ, self.cards, lambda: NOW)

    def seed(self) -> None:
        assert self("seed") == 0
        assert current(self.storage).rev == 1

    def use_llm(self, llm: VetLlm) -> None:
        self.monkeypatch.setattr(job, "make_llm", lambda *args, **kwargs: llm)

    def put(self, name: str, items: Any) -> Path:
        return write_file(self.notes, name, items)


def ok_vet(records: Sequence[MemoryRecord]) -> str | None:
    return None


def zero_measure(knowledge: CurrentKnowledge) -> int:
    return 0


def hand_change(
    storage: LocalStorage,
    upsert: Sequence[MemoryRecord] = (),
    remove: Sequence[str] = (),
    by: str = "synthesizer",
) -> int:
    rev = apply_memory(
        storage,
        MemoryChange(what="зміна руками", why="чому руками", by=by, upsert=list(upsert), remove=list(remove)),
        ok_vet,
        zero_measure,
    )
    assert isinstance(rev, int)
    return rev


def change_files(storage: LocalStorage) -> list[str]:
    return sorted(storage.list("system", CHANGES))


def newest_record(storage: LocalStorage) -> ChangeRecord:
    files = change_files(storage)
    raw = storage.read("system", files[-1])
    assert raw is not None
    return ChangeRecord.model_validate_json(raw)


def snapshot(storage: LocalStorage, prefix: str) -> dict[str, bytes]:
    return {p: storage.read("system", p) or b"" for p in sorted(storage.list("system", prefix))}


def memory(storage: LocalStorage) -> dict[str, MemoryRecord]:
    return {r.id: r for r in current(storage).memory}


def events(out: str, name: str) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for line in out.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if isinstance(obj, dict) and obj.get("event") == name:
            found.append(obj)
    return found
