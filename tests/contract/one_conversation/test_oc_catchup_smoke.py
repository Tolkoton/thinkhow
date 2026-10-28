"""Catch-up contract tests of one-conversation: the smoke script (slice tester).

Written from the contract (.engine/slices/one-conversation.md, «Exit criterion»), not from the script:
«`uv run python scripts/smoke_test_one_conversation.py` … друкує `OK: …`: тема, репліка, 24 год тиші,
репліка → історія другої відповіді дорівнює всім репліками першої сесії; `analyze` → контекст містить усі
проаналізовані репліки, якорі — лише нові.»

The script is executed in-process (runpy, as `__main__`) from the repository root. Its checks are judged by
breaking one fact at a time underneath it, at public names only, and expecting the smoke to fail:
- the history: `thinkhow.workspace.reply` / `retry` are wrapped (in the package and in the defining module)
  so that the `facilitate` they are given receives a damaged `FacilitationContext.history`;
- the context: `thinkhow.learning.analyze.analyze` is wrapped so that the model it is given receives the
  analyzer text without the lines between `CONTEXT` and `NEW`;
- the anchor: `thinkhow.learning.analyze.answer_schema` is wrapped so that the anchor may also be a turn
  that was analyzed already.
Each breakage records that it took place, so a test cannot pass because the breakage missed.
"""

from __future__ import annotations

import dataclasses
import io
import runpy
import sys
from collections.abc import Callable, Iterator, Sequence
from contextlib import redirect_stdout
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest

import thinkhow.learning.analyze as analyze_mod
import thinkhow.workspace as workspace
from thinkhow.facilitation.types import FacilitationContext
from thinkhow.platform.llm import Turn

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "scripts" / "smoke_test_one_conversation.py"


def replace_public(m: pytest.MonkeyPatch, module: Any, name: str, new: Any) -> None:
    """Replace a public function in `module` and in the module that defines it."""
    original = getattr(module, name)
    m.setattr(module, name, new)
    defining = sys.modules[original.__module__]
    if defining is not module and hasattr(defining, name):
        m.setattr(defining, name, new)


def run_smoke(
    monkeypatch: pytest.MonkeyPatch, sabotage: Callable[[pytest.MonkeyPatch], None] | None = None
) -> tuple[bool, str]:
    """Runs the smoke; returns (succeeded, stdout)."""
    out = io.StringIO()
    with monkeypatch.context() as m:
        m.chdir(REPO)
        if sabotage is not None:
            sabotage(m)
        ok = True
        try:
            with redirect_stdout(out):
                runpy.run_path(str(SCRIPT), run_name="__main__")
        except SystemExit as stop:
            ok = stop.code in (0, None)
        except Exception:
            ok = False
    return ok, out.getvalue()


def damage_history(
    change: Callable[[list[Any]], list[Any]], broken: list[int]
) -> Callable[[pytest.MonkeyPatch], None]:
    """`reply` and `retry` hand on a `facilitate` whose context has a history changed by `change`
    whenever the history is not empty (every answer after the topic's first)."""

    def wrap_facilitate(facilitate: Any) -> Any:
        def damaged(ctx: FacilitationContext) -> Iterator[Any]:
            if ctx.history:
                new = change(list(ctx.history))
                if new != list(ctx.history):
                    broken.append(ctx.turn_no)
                    ctx = dataclasses.replace(ctx, history=new)
            events: Iterator[Any] = facilitate(ctx)
            return events

        return damaged

    def wrapping(name: str) -> Callable[..., Any]:
        original = getattr(workspace, name)

        def call(storage: Any, facilitate: Any, *args: Any, **kwargs: Any) -> Any:
            return original(storage, wrap_facilitate(facilitate), *args, **kwargs)

        return call

    def sabotage(m: pytest.MonkeyPatch) -> None:
        replace_public(m, workspace, "reply", wrapping("reply"))
        replace_public(m, workspace, "retry", wrapping("retry"))

    return sabotage


class ContextlessLlm:
    """Passes every call on, except that `generate_json` gets the analyzer text without its context lines."""

    def __init__(self, inner: Any, broken: list[str]) -> None:
        self.inner = inner
        self.broken = broken

    def __getattr__(self, name: str) -> Any:
        return getattr(self.inner, name)

    def generate_json(self, system: str, contents: Sequence[Any], schema: Any, rev: Any) -> Any:
        changed = []
        for turn in contents:
            text = getattr(turn, "text", None)
            if isinstance(text, str) and analyze_mod.CONTEXT in text and analyze_mod.NEW in text:
                head, rest = text.split(analyze_mod.CONTEXT, 1)
                _, tail = rest.split(analyze_mod.NEW, 1)
                stripped = head + analyze_mod.NEW + tail
                self.broken.append(text)
                turn = Turn(turn.role, stripped)
            changed.append(turn)
        return self.inner.generate_json(system, changed, schema, rev)


def test_smoke_passes_and_prints_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    ok, out = run_smoke(monkeypatch)
    assert ok, out
    assert any(line.startswith("OK: ") for line in out.splitlines()), out


def test_smoke_goes_topic_turn_24h_of_silence_turn(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[tuple[Any, Any]] = []
    original = workspace.reply

    def recording(
        storage: Any, facilitate: Any, user: Any, ref: Any, text: str, now: Any, *a: Any, **k: Any
    ) -> Any:
        seen.append((ref, now))
        return original(storage, facilitate, user, ref, text, now, *a, **k)

    ok, out = run_smoke(monkeypatch, lambda m: replace_public(m, workspace, "reply", recording))
    assert ok, out
    assert len(seen) >= 2, seen
    (ref1, now1), (ref2, now2) = seen[0], seen[1]
    assert ref1 == ref2, seen
    assert now2 - now1 > timedelta(hours=24), seen


def test_smoke_fails_when_the_second_answers_history_is_not_every_turn_of_session_1(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    changes: dict[str, Callable[[list[Any]], list[Any]]] = {
        "only the open session (empty)": lambda h: [],
        "the first turn missing": lambda h: h[1:],
        "the turns out of order": lambda h: list(reversed(h)) if len(h) > 1 else h,
    }
    for name, change in changes.items():
        broken: list[int] = []
        ok, out = run_smoke(monkeypatch, damage_history(change, broken))
        assert broken, f"{name}: the breakage did not take place"
        assert not ok, f"{name}: a history of the second answer that is not session 1 was not caught\n{out}"


def test_smoke_fails_when_the_analyzer_context_misses_the_analyzed_turns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    broken: list[str] = []
    original = analyze_mod.analyze

    def contextless(storage: Any, llm: Any, now: Any) -> Any:
        return original(storage, ContextlessLlm(llm, broken), now)

    ok, out = run_smoke(monkeypatch, lambda m: replace_public(m, analyze_mod, "analyze", contextless))
    assert broken, "the breakage did not take place: no analyzer call had a context"
    assert not ok, f"an analyzer call without the analyzed turns as context was not caught\n{out}"


def test_smoke_fails_when_the_anchor_may_be_an_analyzed_turn(monkeypatch: pytest.MonkeyPatch) -> None:
    broken: list[list[int]] = []
    original = analyze_mod.answer_schema

    def wider(turn_nos: Sequence[int]) -> Any:
        nos = list(turn_nos)
        if nos and nos[0] > 1:
            nos = list(range(1, nos[0])) + nos
            broken.append(nos)
        return original(nos)

    ok, out = run_smoke(monkeypatch, lambda m: m.setattr(analyze_mod, "answer_schema", wider))
    assert broken, "the breakage did not take place: no schema after the first analysis"
    assert not ok, f"an anchor allowed on an already analyzed turn was not caught\n{out}"
