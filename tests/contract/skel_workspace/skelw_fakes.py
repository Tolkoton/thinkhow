"""Helpers for the skel-workspace contract tests (slice tester). Built from the contract, not the code.

- SpyStorage: a `LocalStorage` that records every write (`write` and `create_if_absent`) in order.
- ScenarioFacilitate: a `Facilitate` double. Each call takes the next planned script: a `str` is a
  `ReplyDelta`, a `FacilitatorUpdate` is yielded as is, an exception is raised at that point. Every call
  records its `FacilitationContext` and the bytes of every conversation.md at the moment of the call.
  `read_after_update` turns true if anyone advances the stream past a yielded `FacilitatorUpdate`.
- drain: run and drain a reply/retry iterator; `NotImplementedError` always propagates.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from thinkhow.access import CurrentUser
from thinkhow.facilitation.types import (
    FacilitationContext,
    FacilitatorUpdate,
    MapUpdate,
    ReplyDelta,
)
from thinkhow.platform.storage import Bucket, LocalStorage
from thinkhow.workspace import TopicRef

T0 = datetime(2026, 10, 22, 16, 0, 0, tzinfo=UTC)
H24 = timedelta(hours=24)
S1 = timedelta(seconds=1)

ALICE = CurrentUser(id="alice-1", email="alice@example.com", is_owner=False)
BOB = CurrentUser(id="bob_2", email="bob@example.com", is_owner=False)
OWNER = CurrentUser(id="owner-9", email="owner@example.com", is_owner=True)


class LlmUnavailable(Exception):
    """An LlmUnavailable-like failure of the model (Seam 2)."""


@dataclass
class WriteRec:
    op: str
    bucket: Bucket
    path: str
    data: bytes
    content_type: str


class SpyStorage(LocalStorage):
    def __init__(self, root: Path) -> None:
        super().__init__(root)
        self.writes: list[WriteRec] = []

    def write(self, bucket: Bucket, path: str, data: bytes, content_type: str) -> None:
        self.writes.append(WriteRec("write", bucket, path, data, content_type))
        super().write(bucket, path, data, content_type)

    def create_if_absent(self, bucket: Bucket, path: str, data: bytes, content_type: str) -> bool:
        self.writes.append(WriteRec("create_if_absent", bucket, path, data, content_type))
        return super().create_if_absent(bucket, path, data, content_type)


def update(
    reply: str = "Що може піти не так?", phase: str = "p1", updates: Sequence[dict[str, str]] = ()
) -> FacilitatorUpdate:
    return FacilitatorUpdate(
        reply=reply,
        current_phase_id=phase,
        phase_exit_met=False,
        map_updates=[MapUpdate.model_validate(u) for u in updates],
    )


Step = str | FacilitatorUpdate | BaseException


@dataclass
class Call:
    context: FacilitationContext
    files_at_call: dict[str, bytes]


@dataclass
class ScenarioFacilitate:
    storage: LocalStorage
    scripts: list[list[Step]] = field(default_factory=list)
    calls: list[Call] = field(default_factory=list)
    read_after_update: bool = False

    def __call__(self, context: FacilitationContext) -> Iterator[ReplyDelta | FacilitatorUpdate]:
        snapshot = {p: self.storage.read("users", p) or b"" for p in self.storage.list("users", "")}
        self.calls.append(Call(context, snapshot))
        if not self.scripts:
            raise AssertionError("facilitate was called more times than the scenario planned")
        return self._run(self.scripts.pop(0))

    def _run(self, script: list[Step]) -> Iterator[ReplyDelta | FacilitatorUpdate]:
        for step in script:
            if isinstance(step, BaseException):
                raise step
            if isinstance(step, FacilitatorUpdate):
                yield step
                self.read_after_update = True
            else:
                yield ReplyDelta(text=step)


def ok(
    reply: str = "Що може піти не так?", deltas: Sequence[str] = ("Що ", "може?"), **kw: Any
) -> list[Step]:
    return [*deltas, update(reply, **kw)]


def drain(events: Iterator[Any]) -> list[Any]:
    return list(events)


def conv_path(ref: TopicRef) -> str:
    return f"{ref.uid}/{ref.topic_id}/conversation.md"


def map_path(ref: TopicRef) -> str:
    return f"{ref.uid}/{ref.topic_id}/map.json"


def conv_bytes(storage: LocalStorage, ref: TopicRef) -> bytes:
    data = storage.read("users", conv_path(ref))
    assert data is not None
    return data


def conv_lines(storage: LocalStorage, ref: TopicRef) -> list[str]:
    return conv_bytes(storage, ref).decode("utf-8").split("\n")
