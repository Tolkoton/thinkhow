"""Seeding revision 1, publishing a new revision from cards/ and reading the current revision of the Knowledge
(M2 S6, M3 «Посів Знань»; `publish` — slice cards-library); the current state applies the owner's rollbacks by
their provenance (learning-loop S1). Does NOT check versions or remove version files no revision names.
"""

import re
from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import BaseModel

from thinkhow.knowledge.schema import Card, ChangeRecord, MemoryRecord, Rollback
from thinkhow.platform.llm import KnowledgeRev
from thinkhow.platform.storage import Storage

CHANGES = "knowledge/changes/"
CHANGE_FILE = re.compile(r"^knowledge/changes/(\d{6})\.json$")
ROLLBACKS = "knowledge/rollbacks/"
ROLLBACK_FILE = re.compile(r"^knowledge/rollbacks/(\d{6})\.json$")
VERSION_FILE = re.compile(r"^v(\d+)\.json$")
JSON = "application/json"


class KnowledgeMissing(Exception):
    """No change record exists yet: the Knowledge was never seeded."""


class KnowledgeCorrupt(Exception):
    """A change record names a version file that is not there, or disagrees with its own name."""


@dataclass(frozen=True)
class CurrentKnowledge:
    rev: int
    n: int
    cards: dict[str, Card]
    memory: list[MemoryRecord]

    def rev_pair(self) -> KnowledgeRev:
        return KnowledgeRev(rev=self.rev, n=self.n)


@dataclass(frozen=True)
class History:
    """Every change record by rev and every rollback by n, as stored."""

    records: dict[int, ChangeRecord]
    rollbacks: list[Rollback]


@dataclass(frozen=True)
class CurrentPaths:
    """The current state as version paths: the last change record, then the rollbacks by their rule."""

    rev: int
    n: int
    cards: dict[str, str]
    memory: dict[str, str]


def seed(storage: Storage, cards_dir: Path) -> bool:
    """Flow: refuse if any change record exists → read the cards → version files → change record last (Q2)."""
    if _change_revs(storage):
        return False
    cards = _read_cards(cards_dir)
    paths = {card.id: _card_path(card.id, 1) for card in cards}
    for card in cards:
        storage.create_if_absent("system", paths[card.id], card.model_dump_json().encode(), JSON)
    record = ChangeRecord(
        rev=1,
        what=f"посів: {len(cards)} стартових карток",
        why="ревізія 1 з теки cards/ репозиторію",
        cards=paths,
        memory={},
    )
    return storage.create_if_absent("system", _change_path(1), record.model_dump_json().encode(), JSON)


def publish(storage: Storage, cards_dir: Path) -> int | None:
    """Flow: the current record → the folder's cards → version files of the changed ones → change record last.

    None when the folder equals the current revision, or when another run created a file first.
    """
    paths_now = current_paths(storage)
    rev, record, cards = _current_record(storage)
    folder = _read_cards(cards_dir)
    paths: dict[str, str] = {}
    for card in folder:
        if cards.get(card.id) == card:
            paths[card.id] = record.cards[card.id]
            continue
        path = _card_path(card.id, _next_version(storage, card.id))
        if not storage.create_if_absent("system", path, card.model_dump_json().encode(), JSON):
            return None
        paths[card.id] = path
    if paths == record.cards:
        return None
    change = ChangeRecord(
        rev=rev + 1,
        what=_what(record.cards, paths),
        why="нова ревізія з теки cards/ репозиторію (Job cards)",
        cards=paths,
        memory=paths_now.memory,
    )
    created = storage.create_if_absent(
        "system", _change_path(rev + 1), change.model_dump_json().encode(), JSON
    )
    return rev + 1 if created else None


def _current_record(storage: Storage) -> tuple[int, ChangeRecord, dict[str, Card]]:
    """The largest rev, its change record and the cards it names (as `current` reads them)."""
    knowledge = current(storage)
    record = _read_model(storage, _change_path(knowledge.rev), ChangeRecord)
    return knowledge.rev, record, knowledge.cards


def _next_version(storage: Storage, card_id: str) -> int:
    """One more than the largest v<N>.json of this card in the storage; 1 for a new card."""
    prefix = f"knowledge/cards/{card_id}/"
    found = [
        int(m.group(1)) for p in storage.list("system", prefix) if (m := VERSION_FILE.match(p[len(prefix) :]))
    ]
    return max(found, default=0) + 1


def _what(old: dict[str, str], new: dict[str, str]) -> str:
    added = sorted(set(new) - set(old))
    changed = sorted(cid for cid in set(new) & set(old) if new[cid] != old[cid])
    removed = sorted(set(old) - set(new))
    parts = [
        f"{name}: {', '.join(ids)}"
        for name, ids in (("нові", added), ("змінені", changed), ("прибрані", removed))
        if ids
    ]
    return "картки з теки cards/ — " + "; ".join(parts)


def current(storage: Storage) -> CurrentKnowledge:
    """Flow: the current paths (the last record minus the rollbacks) → every version they name (I2)."""
    paths = current_paths(storage)
    cards = {cid: _read_model(storage, path, Card) for cid, path in paths.cards.items()}
    memory = sorted(
        (_read_model(storage, p, MemoryRecord) for p in paths.memory.values()), key=lambda m: m.id
    )
    return CurrentKnowledge(rev=paths.rev, n=paths.n, cards=cards, memory=memory)


def current_paths(storage: Storage) -> CurrentPaths:
    """Flow: the history → the last record → its memory with the rollbacks applied."""
    history = read_history(storage)
    rev = max(history.records)
    record = history.records[rev]
    memory, _ = apply_rollbacks(history, dict(record.memory))
    n = max((rb.n for rb in history.rollbacks), default=0)
    return CurrentPaths(rev=rev, n=n, cards=dict(record.cards), memory=memory)


def read_history(storage: Storage) -> History:
    """Every change record (each checked against its name) and every rollback, by n."""
    revs = _change_revs(storage)
    if not revs:
        raise KnowledgeMissing("the Knowledge has no change record: run `seed` first")
    records = {rev: _read_model(storage, _change_path(rev), ChangeRecord) for rev in revs}
    for rev, record in records.items():
        if record.rev != rev:
            raise KnowledgeCorrupt(f"{_change_path(rev)} says rev {record.rev}")
    rollbacks = sorted(
        (
            _read_model(storage, p, Rollback)
            for p in storage.list("system", ROLLBACKS)
            if ROLLBACK_FILE.match(p)
        ),
        key=lambda rb: rb.n,
    )
    return History(records=records, rollbacks=rollbacks)


def apply_rollbacks(history: History, memory: dict[str, str]) -> tuple[dict[str, str], dict[int, list[str]]]:
    """The rollback rule (learning-loop S1): rollback k of rev R acts on an id only when every later revision
    that replaced that id was itself rolled back for it by an earlier rollback. Returns the memory and, by n,
    the ids each rollback acted on."""
    last = max(history.records)
    acted: set[tuple[int, str]] = set()
    by_n: dict[int, list[str]] = {}
    for rb in history.rollbacks:
        if rb.rev > last:
            raise KnowledgeCorrupt(f"rollback {rb.n} names rev {rb.rev}, after the last record {last}")
        by_n[rb.n] = [mid for mid in sorted(rb.reverts) if _acts(history, acted, rb.rev, mid)]
        for mid in by_n[rb.n]:
            _restore(memory, mid, rb.restore.get(mid))
            acted.add((rb.rev, mid))
    return memory, by_n


def _acts(history: History, acted: set[tuple[int, str]], rev: int, mid: str) -> bool:
    later = (r for r, record in history.records.items() if r > rev and mid in record.replaced)
    return all((r, mid) in acted for r in later)


def _restore(memory: dict[str, str], mid: str, path: str | None) -> None:
    if path is None:
        memory.pop(mid, None)
    else:
        memory[mid] = path


def _change_revs(storage: Storage) -> list[int]:
    return [int(m.group(1)) for path in storage.list("system", CHANGES) if (m := CHANGE_FILE.match(path))]


def _read_cards(cards_dir: Path) -> list[Card]:
    files = sorted(cards_dir.glob("*.yaml"))
    if not files:
        raise ValueError(f"no *.yaml card in {cards_dir}")
    cards = []
    for file in files:
        card = Card.model_validate(yaml.safe_load(file.read_text(encoding="utf-8")))
        if card.id != file.stem:
            raise ValueError(f"{file.name} holds the card {card.id!r}: the file name must be the card id")
        cards.append(card)
    return cards


def _read_model[M: BaseModel](storage: Storage, path: str, model: type[M]) -> M:
    data = storage.read("system", path)
    if data is None:
        raise KnowledgeCorrupt(f"the change record names {path}, which is not there")
    return model.model_validate_json(data)


def _card_path(card_id: str, version: int) -> str:
    return f"knowledge/cards/{card_id}/v{version}.json"


def _change_path(rev: int) -> str:
    return f"{CHANGES}{rev:06d}.json"
