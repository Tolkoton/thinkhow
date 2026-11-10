"""Test gap (overseer, task 726) of B-live (`LiveKnowledge`, .engine/slices/notes-readers.behaviors.md).

A memory change published while a reply is under way — here, during the router's model call — must not reach
that reply: the routing decision's rev, the facilitator's rev and the notes in both instructions come from the
revision the reply started on. The app shares one `LiveKnowledge` between requests, so inside that call
another person's reply takes the new revision too (`now()`). A refresh per field read, a second `now()` inside
the reply, or a reply that reads the shared object instead of its snapshot hands the facilitator revision N+1
while the router decided on revision N (or a rev of one revision beside the memory of another); the next reply
takes N+1 whole.
"""

from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Literal, TypeVar

from pydantic import BaseModel

from thinkhow import knowledge
from thinkhow.facilitation import FacilitationContext, FacilitatorUpdate, ProblemMap, RoutingEvent, respond
from thinkhow.knowledge import MemoryChange, MemoryRecord
from thinkhow.platform.llm import Done, Found, KnowledgeRev, ReplyDelta, ScriptedLlm, Turn
from thinkhow.platform.storage import LocalStorage, Storage
from thinkhow.web.app import LiveKnowledge
from thinkhow.web.local import local_script

CARDS = Path(__file__).resolve().parents[2] / "cards"
M = TypeVar("M", bound=BaseModel)


def _note(name: str, audience: Literal["router", "facilitator"]) -> MemoryRecord:
    return MemoryRecord(
        id=name, title=name, cards=["pre-mortem"], noticed="н", do="р", basis="б", audience=audience
    )


def _publish(storage: Storage, *notes: MemoryRecord) -> int:
    change = MemoryChange(what="w", why="y", by="test", upsert=list(notes), remove=[])
    rev = knowledge.apply_memory(storage, change, lambda records: None, lambda k: 0)
    assert rev is not None
    return rev


class PublishingLlm:
    """ScriptedLlm that records the rev of every call; inside the first one a memory change is published and
    another person's reply starts on the same shared LiveKnowledge."""

    def __init__(self, storage: Storage, live: LiveKnowledge) -> None:
        self.inner = ScriptedLlm(local_script)
        self.storage = storage
        self.live = live
        self.revs: list[KnowledgeRev | None] = []
        self.published: int | None = None

    def stream_json(
        self, system: str, contents: Sequence[Turn], schema: type[BaseModel], rev: KnowledgeRev | None
    ) -> Iterator[ReplyDelta | Done]:
        self._call(rev)
        return self.inner.stream_json(system, contents, schema, rev)

    def generate_json(
        self, system: str, contents: Sequence[Turn], schema: type[M], rev: KnowledgeRev | None
    ) -> M:
        self._call(rev)
        return self.inner.generate_json(system, contents, schema, rev)

    def search_text(self, system: str, prompt: str, rev: KnowledgeRev | None) -> tuple[str, Found | None]:
        return self.inner.search_text(system, prompt, rev)

    def _call(self, rev: KnowledgeRev | None) -> None:
        self.revs.append(rev)
        if self.published is None:
            self.published = _publish(
                self.storage, _note("late-router", "router"), _note("late-fac", "facilitator")
            )
            self.live.now()


def test_a_change_published_inside_a_reply_reaches_neither_call_of_that_reply(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    knowledge.seed(storage, CARDS)
    start = _publish(storage, _note("early-router", "router"), _note("early-fac", "facilitator"))
    live = LiveKnowledge(storage, knowledge.current(storage))
    llm = PublishingLlm(storage, live)
    ctx = FacilitationContext("pre-mortem", [], ProblemMap(), 1, "Хочу відкрити кав'ярню.", None, ())

    events = list(respond(ctx, live, llm))

    routed = [e for e in events if isinstance(e, RoutingEvent)]
    assert routed and routed[0].decision.card_id == "pre-mortem"
    assert any(isinstance(e, FacilitatorUpdate) for e in events)
    assert llm.published == start + 1
    (router_system, _, router_schema), (facilitator_system, _, _) = llm.inner.calls
    assert "action" in router_schema.model_fields
    assert llm.revs == [KnowledgeRev(rev=start, n=0), KnowledgeRev(rev=start, n=0)]
    assert "early-router" in router_system and "late-router" not in router_system
    assert "early-fac" in facilitator_system and "late-fac" not in facilitator_system
    nxt = live.now()
    assert nxt.rev == llm.published and {"late-router", "late-fac"} <= {m.id for m in nxt.memory}
