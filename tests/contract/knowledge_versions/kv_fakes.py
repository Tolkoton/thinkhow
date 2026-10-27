"""Helpers for the knowledge-versions contract tests (slice tester). Built from the contract, not the code.

- RecordingStorage: a LocalStorage that records every write / create_if_absent and can force the result of
  create_if_absent under a prefix, or let a rival writer take a rollback number first.
- card_dict / write_cards / seeded: a real `seed` from a temporary cards folder.
- rec: a MemoryRecord; apply_ok: `apply_memory` with a passing vet and a zero measure.
- snapshot: every file under a LocalStorage root with its bytes.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from thinkhow.knowledge import (
    ChangeRecord,
    CurrentKnowledge,
    MemoryChange,
    MemoryRecord,
    apply_memory,
    current,
    seed,
)
from thinkhow.platform.storage import Bucket, LocalStorage

NOW = datetime(2026, 10, 27, 12, 0, tzinfo=UTC)
CARDS = "knowledge/cards/"
CHANGES = "knowledge/changes/"
ROLLBACKS = "knowledge/rollbacks/"


class RecordingStorage(LocalStorage):
    def __init__(self, root: Path) -> None:
        super().__init__(root)
        self.forced_prefix: tuple[str, bool] | None = None
        # rival(path) is called on a create_if_absent under knowledge/rollbacks/ and may take the path first
        self.rival: Callable[[RecordingStorage, str], None] | None = None
        self.creates: list[tuple[Bucket, str, str]] = []
        self.writes: list[tuple[Bucket, str, str]] = []

    def write(self, bucket: Bucket, path: str, data: bytes, content_type: str) -> None:
        self.writes.append((bucket, path, content_type))
        super().write(bucket, path, data, content_type)

    def create_if_absent(self, bucket: Bucket, path: str, data: bytes, content_type: str) -> bool:
        self.creates.append((bucket, path, content_type))
        if self.forced_prefix is not None and path.startswith(self.forced_prefix[0]):
            return self.forced_prefix[1]
        if self.rival is not None and path.startswith(ROLLBACKS):
            self.rival(self, path)
        return super().create_if_absent(bucket, path, data, content_type)

    def put(self, path: str, data: dict[str, Any]) -> None:
        """A file written by hand (not recorded as the code's write)."""
        data_bytes = json.dumps(data, ensure_ascii=False).encode()
        LocalStorage.write(self, "system", path, data_bytes, "application/json")


def card_dict(cid: str, title: str | None = None) -> dict[str, Any]:
    return {
        "id": cid,
        "title": title if title is not None else f"Картка {cid}",
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


def write_cards(cards_dir: Path, titles: dict[str, str]) -> Path:
    cards_dir.mkdir(parents=True, exist_ok=True)
    for old in cards_dir.glob("*.yaml"):
        old.unlink()
    for cid, title in titles.items():
        text = yaml.safe_dump(card_dict(cid, title), allow_unicode=True, sort_keys=False)
        (cards_dir / f"{cid}.yaml").write_text(text, encoding="utf-8")
    return cards_dir


def seeded(tmp_path: Path, titles: dict[str, str] | None = None) -> RecordingStorage:
    """Revision 1: the real `seed` of the cards alpha, beta (no memory)."""
    store = RecordingStorage(tmp_path / "bucket")
    cards = write_cards(tmp_path / "cards", titles or {"alpha": "Альфа", "beta": "Бета"})
    assert seed(store, cards)
    assert current(store).rev == 1
    return store


def rec(mid: str, noticed: str = "помічено", cards: Sequence[str] = ("alpha",), **extra: Any) -> MemoryRecord:
    return MemoryRecord(
        id=mid,
        title=f"запис {mid}",
        cards=list(cards),
        noticed=noticed,
        do=f"робити {mid}",
        basis=f"підстава {mid}",
        **extra,
    )


def change(
    upsert: Sequence[MemoryRecord] = (), remove: Sequence[str] = (), what: str = "зміна", **extra: Any
) -> MemoryChange:
    return MemoryChange(what=what, why="чому", by="synth", upsert=list(upsert), remove=list(remove), **extra)


def ok_vet(records: Sequence[MemoryRecord]) -> str | None:
    return None


def zero_measure(knowledge: CurrentKnowledge) -> int:
    return 0


def apply_ok(store: LocalStorage, upsert: Sequence[MemoryRecord] = (), remove: Sequence[str] = ()) -> int:
    rev = apply_memory(store, change(upsert, remove), ok_vet, zero_measure)
    assert isinstance(rev, int)
    return rev


def memory(store: LocalStorage) -> dict[str, MemoryRecord]:
    return {record.id: record for record in current(store).memory}


def record(store: LocalStorage, rev: int) -> ChangeRecord:
    data = store.read("system", f"{CHANGES}{rev:06d}.json")
    assert data is not None, rev
    return ChangeRecord.model_validate_json(data)


def mpath(mid: str, k: int) -> str:
    return f"knowledge/memory/{mid}/v{k}.json"


def snapshot(root: Path, prefix: str = "") -> dict[str, bytes]:
    base = root / "system"
    files = (p for p in sorted(base.rglob("*")) if p.is_file())
    return {
        p.relative_to(base).as_posix(): p.read_bytes()
        for p in files
        if p.relative_to(base).as_posix().startswith(prefix)
    }


def vet_says(
    reason: str | None, calls: list[list[MemoryRecord]] | None = None
) -> Callable[[Sequence[MemoryRecord]], str | None]:
    def vet(records: Sequence[MemoryRecord]) -> str | None:
        if calls is not None:
            calls.append(list(records))
        return reason

    return vet


def measure_is(size: int, seen: list[CurrentKnowledge] | None = None) -> Callable[[CurrentKnowledge], int]:
    def measure(knowledge: CurrentKnowledge) -> int:
        if seen is not None:
            seen.append(knowledge)
        return size

    return measure
