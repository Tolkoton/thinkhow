"""Helpers for the research-display contract tests (slice tester; from the contract, not the code).

The sealed helpers of research-quick (`rq_fakes`: the genai fake with grounding metadata, contexts, the
research.json helpers) and of skel-web (`skelweb_fakes`: the app, the IAP fake, the page parser) are reused
as they are: their folders are put on `sys.path`.

- GOOGLE: the prefix of Google's grounding redirect links, word for word from the contract «Seam».
- HeadRecorder: a fake `Head` that answers by plan and records every call.
- RecordingResolve: a fake `resolve` from a dict, recording every url it was called with (thread-safe).
- entry: one record of research.json in the shape research-quick writes it.
- seed_answered: a topic with answered exchanges, made through `workspace.reply`.
"""

from __future__ import annotations

import json
import sys
import threading
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
for sibling in ("research_quick", "skel_web"):
    path = str(HERE.parent / sibling)
    if path not in sys.path:
        sys.path.insert(0, path)

from rq_fakes import ScenarioFacilitate, put_research, upd  # noqa: E402

from thinkhow.access import CurrentUser  # noqa: E402
from thinkhow.facilitation import ReplyDelta  # noqa: E402
from thinkhow.platform.storage import LocalStorage  # noqa: E402
from thinkhow.workspace import Answered, TopicRef, create_topic, reply  # noqa: E402

GOOGLE = "https://vertexaisearch.cloud.google.com/grounding-api-redirect/"

HeadAnswer = tuple[int, str | None] | BaseException


class HeadRecorder:
    def __init__(self, answer: HeadAnswer) -> None:
        self.answer = answer
        self.calls: list[tuple[str, float]] = []

    def __call__(self, url: str, timeout_s: float) -> tuple[int, str | None]:
        self.calls.append((url, timeout_s))
        if isinstance(self.answer, BaseException):
            raise self.answer
        return self.answer


class RecordingResolve:
    def __init__(self, mapping: Mapping[str, str], before: Callable[[str], None] | None = None) -> None:
        self.mapping = dict(mapping)
        self.before = before
        self.calls: list[str] = []
        self.lock = threading.Lock()

    def __call__(self, url: str) -> str:
        with self.lock:
            self.calls.append(url)
        if self.before is not None:
            self.before(url)
        return self.mapping.get(url, url)


def entry(turn: int, suggestions_html: str | None, sources: Sequence[tuple[str, str]] = ()) -> dict[str, Any]:
    return {
        "turn": turn,
        "depth": "quick",
        "queries": ["оренда офісу Лейпциг"],
        "sources": [{"title": t, "url": u} for t, u in sources],
        "suggestions_html": suggestions_html,
        "question": None,
        "report": None,
    }


def write_research(store: LocalStorage, ref: TopicRef, entries: Sequence[dict[str, Any]]) -> None:
    put_research(store, ref, json.dumps({"entries": list(entries)}, ensure_ascii=False).encode())


def seed_answered(
    store: LocalStorage, user: CurrentUser, title: str, exchanges: Sequence[tuple[str, str]], now: Any
) -> TopicRef:
    ref = TopicRef(user.id, create_topic(store, user, title, now))
    for ask, answer in exchanges:
        fac = ScenarioFacilitate([[ReplyDelta(answer), upd(answer)]])
        got = list(reply(store, fac, user, ref, ask, now))
        assert isinstance(got[-1], Answered), got[-1]
    return ref
