"""Catch-up contract tests of skel-facilitation: the smoke script (slice tester).

Written from the contract (.engine/slices/skel-facilitation.md, «Exit criterion»), not the code. The
script is executed in-process (runpy, as `__main__`) from the repository root, with the public
`thinkhow.facilitation.respond` replaced by a scripted double (the same name is replaced in the
submodule `thinkhow.facilitation.respond` too), so its printing and its own checks can be judged
without Vertex. `make_llm` is replaced by a model that refuses every call: with `respond` replaced,
nothing may reach the model. The real-Vertex run is in `test_skelf_catchup_smoke_live.py`.
"""

import io
import os
import runpy
import sys
from collections.abc import Iterator
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any

import pytest

import thinkhow.facilitation as facilitation
import thinkhow.platform.llm as platform_llm
from thinkhow.facilitation import (
    FacilitationContext,
    FacilitatorUpdate,
    MapUpdate,
    ReplyDelta,
)
from thinkhow.knowledge import CurrentKnowledge

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "scripts" / "smoke_test_skel_facilitation.py"
SKIP_DIRS = {".git", ".venv", "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache", "node_modules"}
PHASE = "phase_2_blind_spots"
DELTAS = ["Уявімо, що минуло ", "три місяці й усе провалилося. ", "Що пішло не так?"]
REPLY = "".join(DELTAS)
MAP_TEXT = "Відкрити кав'ярню-обсмажувальню у Львові за три місяці"


class RefusingLlm:
    def stream_json(self, *args: Any, **kwargs: Any) -> Any:
        raise AssertionError("the model was called although respond was replaced")

    def generate_json(self, *args: Any, **kwargs: Any) -> Any:
        raise AssertionError("the model was called although respond was replaced")


def good_update(reply: str = REPLY, phase: str = PHASE) -> FacilitatorUpdate:
    return FacilitatorUpdate(
        reply=reply,
        current_phase_id=phase,
        phase_exit_met=False,
        map_updates=[MapUpdate(op="add", id="i1", type="goal", text=MAP_TEXT, turn="t1")],
    )


class Recorder:
    def __init__(self, items: list[ReplyDelta | FacilitatorUpdate]) -> None:
        self.items = items
        self.calls: list[tuple[FacilitationContext, CurrentKnowledge]] = []

    def __call__(self, *args: Any, **kwargs: Any) -> Iterator[ReplyDelta | FacilitatorUpdate]:
        named = ["ctx", "knowledge", "llm"]
        bound = dict(zip(named, args, strict=False)) | kwargs
        self.calls.append((bound["ctx"], bound["knowledge"]))
        yield from self.items


def run_smoke(monkeypatch: pytest.MonkeyPatch, tmp: Path, fake: Recorder) -> tuple[bool, str]:
    """Runs the smoke with `respond` replaced; returns (succeeded, stdout)."""
    out = io.StringIO()
    with monkeypatch.context() as m:
        m.setattr(facilitation, "respond", fake)
        m.setattr(sys.modules["thinkhow.facilitation.respond"], "respond", fake)
        m.setattr(platform_llm, "make_llm", lambda *a, **k: RefusingLlm())
        for name in ("TMPDIR", "TEMP", "TMP"):
            m.setenv(name, str(tmp))
        m.setattr("tempfile.tempdir", None)
        m.chdir(REPO)
        ok = True
        try:
            with redirect_stdout(out):
                runpy.run_path(str(SCRIPT), run_name="__main__")
        except SystemExit as stop:
            ok = stop.code in (0, None)
        except Exception:
            ok = False
    return ok, out.getvalue()


def knowledge_changes_in_repo() -> set[Path]:
    found: set[Path] = set()
    for root, dirs, files in os.walk(REPO):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        here = Path(root)
        if here.name == "changes" and here.parent.name == "knowledge":
            found.update(here / f for f in files)
    return found


def test_smoke_leads_one_ukrainian_turn_by_pre_mortem_on_seeded_knowledge(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake = Recorder([*(ReplyDelta(d) for d in DELTAS), good_update()])
    ok, _ = run_smoke(monkeypatch, tmp_path, fake)
    assert ok
    assert len(fake.calls) == 1
    ctx, knowledge = fake.calls[0]
    assert ctx.card_id == "pre-mortem"
    assert "pre-mortem" in knowledge.cards
    assert any("Ѐ" <= ch <= "ӿ" for ch in ctx.text), ctx.text


def test_smoke_seeds_knowledge_in_a_temporary_folder_not_in_the_repository(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    before = knowledge_changes_in_repo()
    fake = Recorder([*(ReplyDelta(d) for d in DELTAS), good_update()])
    ok, _ = run_smoke(monkeypatch, tmp_path, fake)
    assert ok
    assert knowledge_changes_in_repo() == before


def test_smoke_prints_the_reply_the_phase_and_the_map_changes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake = Recorder([*(ReplyDelta(d) for d in DELTAS), good_update()])
    ok, out = run_smoke(monkeypatch, tmp_path, fake)
    assert ok
    assert REPLY in out
    assert PHASE in out
    assert MAP_TEXT in out


def test_smoke_fails_on_fewer_than_two_deltas(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fake = Recorder([ReplyDelta(REPLY), good_update()])
    ok, _ = run_smoke(monkeypatch, tmp_path, fake)
    assert not ok, "one delta was not caught"


def test_smoke_fails_when_joined_deltas_differ_from_reply(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake = Recorder([*(ReplyDelta(d) for d in DELTAS), good_update(reply=REPLY + " Інший текст.")])
    ok, _ = run_smoke(monkeypatch, tmp_path, fake)
    assert not ok, "joined deltas != reply was not caught"


def test_smoke_fails_when_the_phase_is_not_of_the_card(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake = Recorder([*(ReplyDelta(d) for d in DELTAS), good_update(phase="phase_9_elsewhere")])
    ok, _ = run_smoke(monkeypatch, tmp_path, fake)
    assert not ok, "a phase outside the card was not caught"
