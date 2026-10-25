"""Helpers for the research-in-conversation block (integration) tests. Slice tester, mode `block`; written
from `.engine/architecture/feature/research-in-conversation.md` and the public signatures, not the bodies.

The sealed helpers of the block's slices are reused as they are (their folders are put on `sys.path`):
`rdp_fakes` (research-deep: `DeepLlm`, the deep scenario; it re-exports `rq` and `fa`) and `skelweb_fakes`
(the web app's identity, settings, SSE reader and page parser).

- facilitate: the product's composition of `Facilitate` — `respond` with a knowledge and a model.
- say: one turn of the person through `workspace.reply`; the events and the text shown live.
- web_app: the real `create_app(Deps(...))` over a local folder, with the given facilitate.
- TwoArgLlm: an `Llm` written the way the sealed fakes are — `Done(raw, usage)` with two arguments and no
  `search_text` method at all.
"""

from __future__ import annotations

import sys
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from functools import partial
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
for sibling in ("research_deep", "research_quick", "fact_answer", "skel_web"):
    path = str(HERE.parent / sibling)
    if path not in sys.path:
        sys.path.insert(0, path)

import rdp_fakes as rdp  # noqa: E402
import skelweb_fakes as sw  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from thinkhow.facilitation import respond  # noqa: E402
from thinkhow.facilitation.types import Facilitate  # noqa: E402
from thinkhow.knowledge import CurrentKnowledge  # noqa: E402
from thinkhow.platform import llm as pl  # noqa: E402
from thinkhow.platform.speech import ScriptedSpeech  # noqa: E402
from thinkhow.platform.storage import LocalStorage  # noqa: E402
from thinkhow.web.server import Deps, create_app  # noqa: E402
from thinkhow.workspace import Delta, TopicRef, open_topic, reply  # noqa: E402

__all__ = [
    "rdp",
    "sw",
    "rq",
    "fa",
    "ALICE",
    "T0",
    "TwoArgLlm",
    "WebApp",
    "facilitate",
    "last_model_text",
    "say",
    "web_app",
]

rq = rdp.rq
fa = rdp.fa
ALICE = rq.ALICE  # the same person id as skelweb_fakes.ALICE ("alice-1"), so H_ALICE logs her in
T0 = rq.T0


def facilitate(llm: Any, knowledge: CurrentKnowledge | None = None) -> Facilitate:
    return partial(respond, knowledge=knowledge if knowledge is not None else rq.knowledge(), llm=llm)


def say(
    store: LocalStorage, fac: Facilitate, ref: TopicRef, text: str, now: datetime = T0
) -> tuple[list[Any], str]:
    got = list(reply(store, fac, ALICE, ref, text, now))
    return got, "".join(e.text for e in got if isinstance(e, Delta))


def last_model_text(store: LocalStorage, ref: TopicRef, now: datetime = T0) -> str:
    turns = [t for s in open_topic(store, ALICE, ref, now).sessions for t in s.turns]
    assert turns and turns[-1].role == "model", turns
    return turns[-1].text


@dataclass
class WebApp:
    client: TestClient
    storage: LocalStorage


def web_app(tmp_path: Path, fac: Facilitate, now: Callable[[], datetime] = lambda: T0) -> WebApp:
    store = LocalStorage(tmp_path / "data")
    deps = Deps(
        storage=store,
        identity=sw.IapIdentity("aud-test", sw.verify_fake),
        settings=sw.settings_for(tmp_path),
        facilitate=fac,
        now=now,
        speech=ScriptedSpeech("(локальний режим) розпізнаний текст"),
    )
    return WebApp(TestClient(create_app(deps), raise_server_exceptions=False, follow_redirects=False), store)


USAGE = pl.Usage(prompt_tokens=10, output_tokens=5, thought_tokens=0)


@dataclass
class TwoArgLlm:
    """The shape of the sealed fakes: `Done(raw, usage)` built with two arguments, no `search_text`."""

    streams: list[tuple[list[str], str]] = field(default_factory=list)
    generate: list[str] = field(default_factory=list)
    kinds: list[str] = field(default_factory=list)

    def stream_json(
        self, system: str, contents: Sequence[pl.Turn], schema: type[BaseModel], rev: pl.KnowledgeRev | None
    ) -> Iterator[pl.ReplyDelta | pl.Done]:
        self.kinds.append("stream")
        deltas, raw = self.streams.pop(0)
        return self._stream(deltas, raw)

    def _stream(self, deltas: list[str], raw: str) -> Iterator[pl.ReplyDelta | pl.Done]:
        for d in deltas:
            yield pl.ReplyDelta(text=d)
        yield pl.Done(raw, USAGE)

    def generate_json(
        self, system: str, contents: Sequence[pl.Turn], schema: type[Any], rev: pl.KnowledgeRev | None
    ) -> Any:
        self.kinds.append("generate")
        return schema.model_validate_json(self.generate.pop(0))
