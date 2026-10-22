"""Disputed catch-up tests of skel-knowledge (question Q1): does the smoke script itself check the results
the exit criterion lists, or only show them? This file takes the stricter reading: a smoke whose seed or
current gives another result must fail. Slice tester; written from the contract, not the code.

The script is executed in-process (runpy, as `__main__`) with `thinkhow.knowledge.seed` / `current`
replaced by wrappers around the real ones — the public names of the package (`публічне — лише з
`__init__.py``); the same names are replaced in `thinkhow.knowledge.store` too.
"""

import dataclasses
import runpy
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

import thinkhow.knowledge as knowledge
import thinkhow.knowledge.store as store
from thinkhow.knowledge import CurrentKnowledge, MemoryRecord

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "scripts" / "smoke_test_skel_knowledge.py"
REAL_SEED = knowledge.seed
REAL_CURRENT = knowledge.current


def smoke_fails(monkeypatch: pytest.MonkeyPatch, name: str, replacement: Callable[..., Any]) -> bool:
    with monkeypatch.context() as m:
        m.setattr(knowledge, name, replacement)
        m.setattr(store, name, replacement)
        m.chdir(REPO)
        try:
            runpy.run_path(str(SCRIPT), run_name="__main__")
        except SystemExit as stop:
            return stop.code not in (0, None)
        except Exception:
            return True
    return False


def test_q1_smoke_fails_when_seed_gives_another_result(monkeypatch: pytest.MonkeyPatch) -> None:
    def always_true(*args: Any, **kwargs: Any) -> bool:
        REAL_SEED(*args, **kwargs)
        return True

    def always_false(*args: Any, **kwargs: Any) -> bool:
        REAL_SEED(*args, **kwargs)
        return False

    assert not smoke_fails(monkeypatch, "seed", REAL_SEED), "the smoke fails with the real seed"
    assert smoke_fails(monkeypatch, "seed", always_true), "second seed → True was not caught"
    assert smoke_fails(monkeypatch, "seed", always_false), "first seed → False was not caught"


def test_q1_smoke_fails_when_current_gives_another_result(monkeypatch: pytest.MonkeyPatch) -> None:
    stray = MemoryRecord(id="M-001", title="t", cards=["pre-mortem"], noticed="n", do="d", basis="b")
    changes: list[Callable[[CurrentKnowledge], CurrentKnowledge]] = [
        lambda ck: dataclasses.replace(ck, rev=2),
        lambda ck: dataclasses.replace(ck, n=1),
        lambda ck: dataclasses.replace(ck, cards={}),
        lambda ck: dataclasses.replace(ck, memory=[stray]),
    ]
    assert not smoke_fails(monkeypatch, "current", REAL_CURRENT), "the smoke fails with the real current"
    for number, change in enumerate(changes):

        def wrong(
            *args: Any, _change: Callable[[CurrentKnowledge], CurrentKnowledge] = change, **kwargs: Any
        ) -> CurrentKnowledge:
            return _change(REAL_CURRENT(*args, **kwargs))

        assert smoke_fails(monkeypatch, "current", wrong), f"change {number} of current was not caught"
