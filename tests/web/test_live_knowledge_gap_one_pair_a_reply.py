"""Test gap (overseer, task 725) of B-live (`LiveKnowledge`, .engine/slices/notes-readers.behaviors.md).

A refresh per field read (the four fields re-listed on every access) or a re-read of the Knowledge on every
reply does storage work that grows with the number of notes. One full reply — the router chooses the card,
the card's facilitator answers — must list the newest revision exactly once (`latest_pair`, two listings) and
read nothing while nothing new is listed, whatever the number of notes.
"""

from pathlib import Path

import pytest

from thinkhow import knowledge
from thinkhow.facilitation import FacilitationContext, FacilitatorUpdate, ProblemMap, RoutingEvent, respond
from thinkhow.knowledge import MemoryChange, MemoryRecord
from thinkhow.platform.llm import ScriptedLlm
from thinkhow.platform.storage import Bucket, LocalStorage, Storage
from thinkhow.web.app import LiveKnowledge
from thinkhow.web.local import local_script

CARDS = Path(__file__).resolve().parents[2] / "cards"


class CountingStorage:
    """LocalStorage that counts every listing and every read."""

    def __init__(self, inner: Storage) -> None:
        self.inner = inner
        self.lists = 0
        self.reads = 0

    def read(self, bucket: Bucket, path: str) -> bytes | None:
        self.reads += 1
        return self.inner.read(bucket, path)

    def write(self, bucket: Bucket, path: str, data: bytes, content_type: str) -> None:
        self.inner.write(bucket, path, data, content_type)

    def create_if_absent(self, bucket: Bucket, path: str, data: bytes, content_type: str) -> bool:
        return self.inner.create_if_absent(bucket, path, data, content_type)

    def list(self, bucket: Bucket, prefix: str) -> list[str]:
        self.lists += 1
        return self.inner.list(bucket, prefix)

    def delete(self, bucket: Bucket, path: str) -> None:
        self.inner.delete(bucket, path)


def _notes(count: int) -> list[MemoryRecord]:
    """Half for the router, half for the facilitator of pre-mortem, so both readers see notes."""
    return [
        MemoryRecord(
            id=f"n-{k}",
            title=f"t{k}",
            cards=["pre-mortem"],
            noticed="н",
            do="р",
            basis="б",
            audience="router" if k % 2 else "facilitator",
        )
        for k in range(count)
    ]


@pytest.mark.parametrize("count", [0, 1, 40])
def test_one_full_reply_lists_once_and_reads_nothing_whatever_the_number_of_notes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, count: int
) -> None:
    storage = CountingStorage(LocalStorage(tmp_path))
    knowledge.seed(storage, CARDS)
    if count:
        change = MemoryChange(what="w", why="y", by="test", upsert=_notes(count), remove=[])
        knowledge.apply_memory(storage, change, lambda records: None, lambda k: 0)
    live = LiveKnowledge(storage, knowledge.current(storage))
    pairs: list[int] = []
    real = knowledge.latest_pair

    def counted(s: Storage) -> tuple[int, int]:
        pairs.append(1)
        return real(s)

    monkeypatch.setattr(knowledge, "latest_pair", counted)
    storage.lists = storage.reads = 0
    llm = ScriptedLlm(local_script)
    ctx = FacilitationContext("pre-mortem", [], ProblemMap(), 1, "Хочу відкрити кав'ярню.", None, ())

    events = list(respond(ctx, live, llm))

    routed = [e for e in events if isinstance(e, RoutingEvent)]
    assert routed and routed[0].decision.card_id == "pre-mortem"
    assert any(isinstance(e, FacilitatorUpdate) for e in events)
    assert len(llm.calls) == 2 and "action" in llm.calls[0][2].model_fields
    assert len(pairs) == 1
    assert (storage.lists, storage.reads) == (2, 0)
    assert all(f"- t{k}." in llm.calls[0][0] for k in range(1, count, 2))
