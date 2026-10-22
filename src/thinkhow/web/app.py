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
from thinkhow.facilitation import respond
from thinkhow.platform.config import load_settings
from thinkhow.platform.identity import make_identity
from thinkhow.platform.llm import make_llm
from thinkhow.platform.storage import make_storage
from thinkhow.web.local import local_script
from thinkhow.web.server import Deps, create_app

CARDS_DIR = Path(__file__).resolve().parents[3] / "cards"


def build_deps(environ: Mapping[str, str], cards_dir: Path) -> Deps:
    """Flow: settings → storage → (local: seed) → current Knowledge → model → facilitate → identity (Q2)."""
    settings = load_settings(environ)
    storage = make_storage(settings)
    if settings.local:
        knowledge.seed(storage, cards_dir)
    current = knowledge.current(storage)
    llm = make_llm(settings, local_script)
    facilitate = functools.partial(respond, knowledge=current, llm=llm)
    return Deps(storage, make_identity(settings), settings, facilitate, lambda: datetime.now(UTC))


def __getattr__(name: str) -> FastAPI:
    if name != "app":
        raise AttributeError(name)
    import os

    return create_app(build_deps(os.environ, CARDS_DIR))
