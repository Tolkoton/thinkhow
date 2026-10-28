"""Composition root of the web service: settings → adapters → Knowledge → facilitate → the app.

`uvicorn thinkhow.web.app:app` (PYTHONPATH=src) reads `app`; it is built on first access from os.environ,
so importing build_deps needs no environment.
"""

import functools
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI

from thinkhow import knowledge
from thinkhow.facilitation import recognize_step, respond
from thinkhow.platform.config import load_settings
from thinkhow.platform.identity import make_identity
from thinkhow.platform.llm import make_llm
from thinkhow.platform.speech import make_speech
from thinkhow.platform.storage import Storage, make_storage
from thinkhow.platform.tts import make_tts
from thinkhow.web.local import local_found, local_script, local_search
from thinkhow.web.server import Deps, create_app

CARDS_DIR = Path(__file__).resolve().parents[3] / "cards"


def build_deps(environ: Mapping[str, str], cards_dir: Path) -> Deps:
    """Flow: settings → storage → (local: seed) → Knowledge → model → facilitate → identity, speech (Q2)."""
    settings = load_settings(environ)
    storage = make_storage(settings)
    if settings.local:
        knowledge.seed(storage, cards_dir)
    current = knowledge.current(storage)
    llm = make_llm(settings, local_script, search=True, found_script=local_found, search_script=local_search)
    facilitate = functools.partial(respond, knowledge=LiveKnowledge(storage, current), llm=llm)

    identity, speech = make_identity(settings), make_speech(settings)
    return Deps(
        storage,
        identity,
        settings,
        facilitate,
        lambda: datetime.now(UTC),
        speech,
        make_tts(settings),
        current.cards,
        lambda step, question, text: recognize_step(step, question, text, llm),
    )


class LiveKnowledge(knowledge.CurrentKnowledge):
    """The current revision for every reply (learning-loop S4, B-live): `now()` lists the newest change record
    and rollback once (`latest_pair`, two listings) and, when they are newer, reads the Knowledge again, so a
    note the synthesizer added or the owner rolled back acts at once (M2 S6). `respond` calls `now()` once per
    reply and reads a plain snapshot. A revision with other cards (`job cards`) is not taken: new cards come
    with the restart of the service, as before (the method captions of `Deps.cards` too)."""

    _storage: Storage
    _pair: tuple[int, int]

    def __init__(self, storage: Storage, first: knowledge.CurrentKnowledge) -> None:
        super().__init__(first.rev, first.n, first.cards, first.memory)
        object.__setattr__(self, "_storage", storage)
        object.__setattr__(self, "_pair", knowledge.latest_pair(storage))

    def now(self) -> knowledge.CurrentKnowledge:
        latest = knowledge.latest_pair(self._storage)
        if latest != self._pair:
            fresh = knowledge.current(self._storage)
            if fresh.cards == self.cards:  # new cards wait for the restart, as before
                for name in ("rev", "n", "memory"):
                    object.__setattr__(self, name, getattr(fresh, name))
            object.__setattr__(self, "_pair", latest)
        return knowledge.CurrentKnowledge(rev=self.rev, n=self.n, cards=self.cards, memory=self.memory)


def __getattr__(name: str) -> FastAPI:
    if name != "app":
        raise AttributeError(name)
    import os

    return create_app(build_deps(os.environ, CARDS_DIR))
