"""Seeding revision 1 and reading the current revision of the Knowledge (M2 S6, M3 «Посів Знань»).

Does NOT write revisions beyond the seed, apply rollbacks or check versions (F11).
"""

import re
from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import BaseModel

from thinkhow.knowledge.schema import Card, ChangeRecord, MemoryRecord
from thinkhow.platform.llm import KnowledgeRev
from thinkhow.platform.storage import Storage

CHANGES = "knowledge/changes/"
CHANGE_FILE = re.compile(r"^knowledge/changes/(\d{6})\.json$")
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


def current(storage: Storage) -> CurrentKnowledge:
    """Flow: the change record with the largest rev → every version it names (I2)."""
    revs = _change_revs(storage)
    if not revs:
        raise KnowledgeMissing("the Knowledge has no change record: run `seed` first")
    rev = max(revs)
    record = _read_model(storage, _change_path(rev), ChangeRecord)
    if record.rev != rev:
        raise KnowledgeCorrupt(f"{_change_path(rev)} says rev {record.rev}")
    cards = {cid: _read_model(storage, path, Card) for cid, path in record.cards.items()}
    memory = sorted(
        (_read_model(storage, p, MemoryRecord) for p in record.memory.values()), key=lambda m: m.id
    )
    return CurrentKnowledge(rev=rev, n=0, cards=cards, memory=memory)


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
