"""notes-readers, self-added B-live (.engine/slices/notes-readers.behaviors.md): the app's facilitation
reads the current revision of the Knowledge on every reply, so a note the synthesizer added or the owner
rolled back acts at once (M2 S6 «відкат діє одразу»)."""

from datetime import UTC, datetime
from pathlib import Path

from thinkhow import knowledge
from thinkhow.knowledge import MemoryChange, MemoryRecord
from thinkhow.platform.storage import LocalStorage
from thinkhow.web.app import LiveKnowledge

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
    assert live.memory == []
    change = MemoryChange(what="w", why="y", by="test", upsert=[NOTE], remove=[])
    rev = knowledge.apply_memory(storage, change, lambda records: None, lambda k: 0)
    assert [m.id for m in live.memory] == [NOTE.id] and live.rev_pair().rev == rev
    knowledge.rollback(storage, rev or 0, "owner", datetime.now(UTC))
    assert live.memory == [] and live.n == 1 and isinstance(live, knowledge.CurrentKnowledge)


def test_live_knowledge_reads_nothing_again_while_nothing_new_is_listed(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    knowledge.seed(storage, CARDS)
    first = knowledge.current(storage)
    live = LiveKnowledge(storage, first)
    assert live.cards is first.cards and live.memory is first.memory


def test_live_knowledge_does_not_take_a_revision_with_other_cards(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path / "data")
    one = tmp_path / "one"
    one.mkdir()
    (one / "pre-mortem.yaml").write_bytes((CARDS / "pre-mortem.yaml").read_bytes())
    knowledge.seed(storage, one)
    live = LiveKnowledge(storage, knowledge.current(storage))
    assert knowledge.publish(storage, CARDS) == 2
    assert live.rev == 1 and list(live.cards) == ["pre-mortem"]
