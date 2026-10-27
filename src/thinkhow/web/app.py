"""Composition root of the web service: settings → adapters → Knowledge → facilitate → the app.

`uvicorn thinkhow.web.app:app` (PYTHONPATH=src) reads `app`; it is built on first access from os.environ,
so importing build_deps needs no environment.
"""

import functools
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from fastapi import FastAPI

from thinkhow import knowledge
from thinkhow.facilitation import respond
from thinkhow.platform.config import load_settings
from thinkhow.platform.identity import make_identity
from thinkhow.platform.llm import make_llm
from thinkhow.platform.speech import make_speech
from thinkhow.platform.storage import Storage, make_storage
from thinkhow.platform.tts import make_tts
from thinkhow.web.local import local_found, local_script, local_search
from thinkhow.web.server import Deps, create_app

CARDS_DIR = Path(__file__).resolve().parents[3] / "cards"
LIVE_FIELDS = frozenset({"rev", "n", "cards", "memory"})


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
    )


class LiveKnowledge(knowledge.CurrentKnowledge):
    """The current revision on every reply (learning-loop S4, B-live): the four fields are read from the
    Knowledge again whenever a newer change record or rollback is listed (two listings, no reads otherwise),
    so a note the synthesizer added or the owner rolled back acts at once (M2 S6). A revision with other cards
    (`job cards`) is not taken: new cards come with the restart of the service, as before (the method
    captions of `Deps.cards` too). It stays a CurrentKnowledge, so facilitation reads it as before."""

    def __init__(self, storage: Storage, first: knowledge.CurrentKnowledge) -> None:
        super().__init__(first.rev, first.n, first.cards, first.memory)
        object.__setattr__(self, "_storage", storage)
        object.__setattr__(self, "_held", (knowledge.latest_pair(storage), first))

    def __getattribute__(self, name: str) -> Any:
        if name in LIVE_FIELDS:
            return getattr(object.__getattribute__(self, "_fresh")(), name)
        return object.__getattribute__(self, name)

    def _fresh(self) -> knowledge.CurrentKnowledge:
        storage = object.__getattribute__(self, "_storage")
        pair, held = cast(
            tuple[tuple[int, int], knowledge.CurrentKnowledge], object.__getattribute__(self, "_held")
        )
        latest = knowledge.latest_pair(storage)
        if latest != pair:
            fresh = knowledge.current(storage)
            held = fresh if fresh.cards == held.cards else held  # new cards wait for the restart, as before
            object.__setattr__(self, "_held", (latest, held))
        return held


def __getattr__(name: str) -> FastAPI:
    if name != "app":
        raise AttributeError(name)
    import os

    return create_app(build_deps(os.environ, CARDS_DIR))
