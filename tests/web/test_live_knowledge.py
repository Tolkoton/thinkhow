"""notes-readers, self-added B-live (.engine/slices/notes-readers.behaviors.md): the app's facilitation
reads the current revision of the Knowledge on every reply, so a note the synthesizer added or the owner
rolled back acts at once (M2 S6 «відкат діє одразу»)."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from thinkhow import knowledge
from thinkhow.facilitation import FacilitationContext, ProblemMap, respond
from thinkhow.knowledge import MemoryChange, MemoryRecord
from thinkhow.platform.llm import ScriptedLlm
from thinkhow.platform.storage import LocalStorage, Storage
from thinkhow.web.app import LiveKnowledge
from thinkhow.web.local import local_script

CARDS = Path(__file__).resolve().parents[2] / "cards"
NOTE = MemoryRecord(
    id="pre-mortem-facilitator",
    title="нотатка",
    cards=["pre-mortem"],
    noticed="помітили",
    do="робити",
    basis="тест",
)


def test_live_knowledge_follows_a_new_revision_and_a_rollback(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    knowledge.seed(storage, CARDS)
    live = LiveKnowledge(storage, knowledge.current(storage))
    assert live.now().memory == []
    change = MemoryChange(what="w", why="y", by="test", upsert=[NOTE], remove=[])
    rev = knowledge.apply_memory(storage, change, lambda records: None, lambda k: 0)
    assert [m.id for m in live.now().memory] == [NOTE.id] and live.now().rev_pair().rev == rev
    knowledge.rollback(storage, rev or 0, "owner", datetime.now(UTC))
    snapshot = live.now()
    assert snapshot.memory == [] and snapshot.n == 1 and type(snapshot) is knowledge.CurrentKnowledge


def test_live_knowledge_reads_nothing_again_while_nothing_new_is_listed(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    knowledge.seed(storage, CARDS)
    first = knowledge.current(storage)
    live = LiveKnowledge(storage, first)
    assert live.now().cards is first.cards and live.now().memory is first.memory


def test_live_knowledge_does_not_take_a_revision_with_other_cards(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path / "data")
    one = tmp_path / "one"
    one.mkdir()
    (one / "pre-mortem.yaml").write_bytes((CARDS / "pre-mortem.yaml").read_bytes())
    knowledge.seed(storage, one)
    live = LiveKnowledge(storage, knowledge.current(storage))
    assert knowledge.publish(storage, CARDS) == 2
    assert live.now().rev == 1 and list(live.now().cards) == ["pre-mortem"]


def test_one_reply_lists_the_newest_revision_once_and_reads_one_revision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The overseer's gaps: one listing a reply whatever the number of notes; one revision a reply."""
    storage = LocalStorage(tmp_path)
    knowledge.seed(storage, CARDS)
    notes = [
        MemoryRecord(
            id=f"n-{k}",
            title=f"t{k}",
            cards=["pre-mortem"],
            noticed="н",
            do="р",
            basis="б",
            audience="router",
        )
        for k in range(25)
    ]
    change = MemoryChange(what="w", why="y", by="test", upsert=notes, remove=[])
    rev = knowledge.apply_memory(storage, change, lambda records: None, lambda k: 0)
    live = LiveKnowledge(storage, knowledge.current(storage))
    calls: list[int] = []
    real = knowledge.latest_pair

    def counted(s: Storage) -> tuple[int, int]:
        calls.append(1)
        return real(s)

    monkeypatch.setattr(knowledge, "latest_pair", counted)
    llm = ScriptedLlm(local_script)
    ctx = FacilitationContext("pre-mortem", [], ProblemMap(), 1, "Хочу відкрити кав'ярню.", None, ())
    list(respond(ctx, live, llm))
    assert len(calls) == 1
    system = llm.calls[0][0]
    assert all(f"- t{k}." in system for k in range(25)) and rev == live.now().rev
