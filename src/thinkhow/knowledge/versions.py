"""Memory changes as revisions of the Knowledge, the owner's rollbacks, the change feed (learning-loop S1).

A memory change passes the version check (ids, cards, size budget, no people's details) and writes new memory
version files and one change record; the cards of the record stay those of the current state. A rollback is a
file of its own; `store.current()` applies it. Does NOT write card files, roll cards back or call a model
itself (the person-details check is the injected `vet`).
"""

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from thinkhow.knowledge.schema import ChangeRecord, MemoryRecord, Rollback
from thinkhow.knowledge.store import (
    ROLLBACKS,
    CurrentKnowledge,
    CurrentPaths,
    History,
    apply_rollbacks,
    current,
    current_paths,
    read_history,
)
from thinkhow.platform.storage import Storage

# The window of a Pro-class model (PR-31: Vertex gives none; the documented 1 048 576 input tokens), a reserve
# of 200 000 tokens for the conversation, 2 characters a token. PROVISIONAL — owner ratification pending.
BUDGET_CHARS = (1_048_576 - 200_000) * 2

JSON = "application/json"
VERSION_FILE = re.compile(r"^v(\d+)\.json$")
ROLLBACK_ATTEMPTS = 4  # the first and three more (knowledge-versions Q1)

Vet = Callable[[Sequence[MemoryRecord]], str | None]
Measure = Callable[[CurrentKnowledge], int]


class VersionRejected(Exception):
    """The version check refused the change; nothing was written."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class UnknownRevision(Exception):
    """No change record has this rev."""


class NotRollbackable(Exception):
    """The revision changed no memory (seed, publish): it cannot be rolled back."""


class AlreadyRolledBack(Exception):
    """A rollback of this revision exists already."""


class KnowledgeConflict(Exception):
    """Another writer kept taking the next rollback number."""


class MemoryChange(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    what: str
    why: str
    by: str
    upsert: list[MemoryRecord]
    remove: list[str]
    observations: list[str] = []


@dataclass(frozen=True)
class ChangeView:
    rev: int
    what: str
    why: str
    by: str
    observations: list[str]
    upserted: list[MemoryRecord]
    removed: list[str]
    rolled_back: int | None
    rollback_changed: list[str]


def apply_memory(storage: Storage, change: MemoryChange, vet: Vet, measure: Measure) -> int | None:
    """Flow: the current state → the version check → version files of the changed records → the record last.

    None when nothing changes, or when another run created a file first (as `publish`).
    """
    paths, knowledge = current_paths(storage), current(storage)
    now = {record.id: record for record in knowledge.memory}
    _check_ids(change, now)
    _check_cards(change, knowledge)
    changed = [record for record in change.upsert if now.get(record.id) != record]
    _check_budget(knowledge, now, change, measure)
    _check_people(changed, vet)
    if not changed and not change.remove:
        return None
    written = _write_versions(storage, changed)
    if written is None:
        return None
    return _write_record(storage, paths, change, written)


def _check_ids(change: MemoryChange, now: dict[str, MemoryRecord]) -> None:
    ids = [record.id for record in change.upsert]
    if len(set(ids)) != len(ids):
        raise VersionRejected("той самий запис двічі серед змін")
    if both := sorted(set(ids) & set(change.remove)):
        raise VersionRejected(f"запис і змінено, і прибрано: {', '.join(both)}")
    if missing := sorted(set(change.remove) - set(now)):
        raise VersionRejected(f"прибрати можна лише чинний запис: {', '.join(missing)}")


def _check_cards(change: MemoryChange, knowledge: CurrentKnowledge) -> None:
    for record in change.upsert:
        if not record.cards:
            raise VersionRejected(f"запис {record.id} не називає жодної картки")
        if unknown := sorted(set(record.cards) - set(knowledge.cards)):
            raise VersionRejected(f"запис {record.id} називає невідомі картки: {', '.join(unknown)}")


def _check_budget(
    knowledge: CurrentKnowledge, now: dict[str, MemoryRecord], change: MemoryChange, measure: Measure
) -> None:
    memory = {mid: record for mid, record in now.items() if mid not in change.remove}
    memory |= {record.id: record for record in change.upsert}
    prospective = CurrentKnowledge(
        rev=knowledge.rev,
        n=knowledge.n,
        cards=knowledge.cards,
        memory=[memory[mid] for mid in sorted(memory)],
    )
    if (size := measure(prospective)) > BUDGET_CHARS:
        raise VersionRejected(f"перевищено бюджет: {size} символів при межі {BUDGET_CHARS}")


def _check_people(changed: Sequence[MemoryRecord], vet: Vet) -> None:
    if changed and (reason := vet(changed)) is not None:
        raise VersionRejected(f"подробиці людей: {reason}")


def _write_versions(storage: Storage, changed: Sequence[MemoryRecord]) -> dict[str, str] | None:
    """A new version file of every changed record; None when another run took a name first."""
    written: dict[str, str] = {}
    for record in changed:
        path = f"knowledge/memory/{record.id}/v{_next_version(storage, record.id)}.json"
        if not storage.create_if_absent("system", path, record.model_dump_json().encode(), JSON):
            return None
        written[record.id] = path
    return written


def _next_version(storage: Storage, mid: str) -> int:
    prefix = f"knowledge/memory/{mid}/"
    found = [
        int(m.group(1)) for p in storage.list("system", prefix) if (m := VERSION_FILE.match(p[len(prefix) :]))
    ]
    return max(found, default=0) + 1


def _write_record(
    storage: Storage, paths: CurrentPaths, change: MemoryChange, written: dict[str, str]
) -> int | None:
    memory = {mid: path for mid, path in paths.memory.items() if mid not in change.remove} | written
    touched = sorted(set(written) | set(change.remove))
    record = ChangeRecord(
        rev=paths.rev + 1,
        what=change.what,
        why=change.why,
        cards=paths.cards,
        memory=memory,
        observations=change.observations,
        by=change.by,
        replaced={mid: paths.memory.get(mid) for mid in touched},
    )
    path = f"knowledge/changes/{record.rev:06d}.json"
    return (
        record.rev
        if storage.create_if_absent("system", path, record.model_dump_json().encode(), JSON)
        else None
    )


def rollback(storage: Storage, rev: int, by: str, now: datetime) -> int:
    """Flow: check the revision → what it set and what was before → the rollback file, next free n."""
    if now.tzinfo is None:
        raise ValueError("now must carry a time zone")
    history = read_history(storage)
    record = _rollbackable(history, rev)
    for _ in range(ROLLBACK_ATTEMPTS):
        candidate = _candidate(history, record, by, now)
        path = f"{ROLLBACKS}{candidate.n:06d}.json"
        if storage.create_if_absent("system", path, candidate.model_dump_json().encode(), JSON):
            return candidate.n
        history = read_history(storage)
    raise KnowledgeConflict(f"no free rollback number after {ROLLBACK_ATTEMPTS} attempts")


def _rollbackable(history: History, rev: int) -> ChangeRecord:
    record = history.records.get(rev)
    if record is None:
        raise UnknownRevision(f"no change record has rev {rev}")
    if not record.replaced:
        raise NotRollbackable(f"rev {rev} changed no memory")
    if any(rb.rev == rev for rb in history.rollbacks):
        raise AlreadyRolledBack(f"rev {rev} is rolled back already")
    return record


def _candidate(history: History, record: ChangeRecord, by: str, now: datetime) -> Rollback:
    """The rollback with the next n; `changed` — the ids the rule lets it act on in the history as it is."""
    n = max((rb.n for rb in history.rollbacks), default=0) + 1
    draft = Rollback(
        n=n,
        rev=record.rev,
        reverts={mid: record.memory.get(mid) for mid in record.replaced},
        restore=dict(record.replaced),
        changed=[],
        at=now,
        by=by,
    )
    future = History(records=history.records, rollbacks=[*history.rollbacks, draft])
    last = history.records[max(history.records)]
    _, acted = apply_rollbacks(future, dict(last.memory))
    return draft.model_copy(update={"changed": acted[n]})


def changes(storage: Storage) -> list[ChangeView]:
    """Every revision, newest first, with what it upserted and removed and its rollback (the smallest n)."""
    history = read_history(storage)
    last = history.records[max(history.records)]
    _, acted = apply_rollbacks(history, dict(last.memory))
    first: dict[int, Rollback] = {}
    for rb in history.rollbacks:
        first.setdefault(rb.rev, rb)
    return [
        _view(storage, history.records[rev], first.get(rev), acted)
        for rev in sorted(history.records, reverse=True)
    ]


def _view(
    storage: Storage, record: ChangeRecord, rb: Rollback | None, acted: dict[int, list[str]]
) -> ChangeView:
    upserted = [
        MemoryRecord.model_validate_json(storage.read("system", record.memory[mid]) or b"")
        for mid in sorted(record.replaced)
        if mid in record.memory
    ]
    return ChangeView(
        rev=record.rev,
        what=record.what,
        why=record.why,
        by=record.by,
        observations=list(record.observations),
        upserted=upserted,
        removed=sorted(mid for mid in record.replaced if mid not in record.memory),
        rolled_back=rb.n if rb else None,
        rollback_changed=acted.get(rb.n, []) if rb else [],
    )
