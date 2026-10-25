"""Harness for the catch-up tests of the product-cards smoke (slice tester; from the contract, not the code).

The smoke `scripts/smoke_test_product_cards.py` is executed in-process (runpy, as `__main__`) from the
repository root, with the public `thinkhow.facilitation.route` replaced by a scripted double and
`thinkhow.platform.llm.make_llm` replaced by a model that refuses every call (with `route` replaced,
nothing may reach the model). The exit code follows Python's own rule: `SystemExit(n)` gives `n`, an
uncaught exception gives 1. Every artifact the run writes into `.engine/artifacts/spikes/` is read back
and removed; files that were there before are left alone.
"""

from __future__ import annotations

import io
import runpy
import sys
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

import thinkhow.facilitation as facilitation
import thinkhow.platform.llm as platform_llm
from thinkhow.facilitation import Candidate, FacilitationContext, RouterAnswer
from thinkhow.facilitation.types import Profile
from thinkhow.knowledge import CurrentKnowledge

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "scripts" / "smoke_test_product_cards.py"
SPIKES = REPO / ".engine" / "artifacts" / "spikes"
ARTIFACT_PREFIX = "product-cards-router-live-"

NEW_IDS = [
    "customer-interviews", "demand-test", "positioning", "offer-design", "value-pricing", "traction-channels",
    "unit-economics",
]  # fmt: skip

# Turn #1 of the owner's topic t-84d1517cb1c1, copied by hand from
# .engine/artifacts/advice-live/2026-10-25T174143Z-t-84d1517cb1c1/conversation.md («### #1 Людина»).
OWNER_TURN_1 = (
    "Так, в мене є така думка зробити для керівників невеликих підприємств і фрілансерів типу "
    "персонального асистента на OpenCore. І, е-е ну, ясно, що типу шляхом курсів помогти його підняти, "
    "настроїти. Ну, таке, що типу ми ведемо тебе за ручку, ти собі то все настроюєш. Е-е і додати в пакет "
    "якийсь там, ну, наприклад, цього думального асистента, додати додати всі мої фреймворки по гормоці, "
    "по маркетингу може, інформація, щоб вони могли робити собі сайти, ну, таке всяке. Е-е як це продати?"
)

PROFILE = Profile(
    intent="plan_execution",
    structuredness="ill_structured",
    reversibility="two_way_door",
    stakes="medium",
    data="data_poor_speculative",
    options="none_exist",
    emotion="neutral_analytical",
    social="product_or_team",
)

OFFER_REPLY = "Ось якими способами можна над цим подумати — оберіть ближчий."
WHY_DT = "перевірити попит малим тестом до того, як будувати пакет"
WHY_JTBD = "зрозуміти, за яку роботу керівник найме такого асистента"
ASK_REPLY = "Кому саме ви хочете це продавати першими — керівникам чи фрілансерам?"
ASK_WHY = "бракує, кому продавати"


def offer(*pairs: tuple[str, str]) -> RouterAnswer:
    return RouterAnswer(
        action="offer",
        profile=PROFILE,
        candidates=[Candidate(card_id=c, why=w) for c, w in pairs],
        card_id=None,
        reply=OFFER_REPLY,
        why="людина питає, як продати задум",
    )


def good_offer() -> RouterAnswer:
    return offer(("demand-test", WHY_DT), ("jobs-to-be-done", WHY_JTBD))


def ask(reply: str = ASK_REPLY) -> RouterAnswer:
    return RouterAnswer(action="ask", profile=PROFILE, candidates=[], card_id=None, reply=reply, why=ASK_WHY)


def choose(card: str = "demand-test") -> RouterAnswer:
    return RouterAnswer(
        action="choose", profile=PROFILE, candidates=[], card_id=card, reply=None, why="людина назвала спосіб"
    )


def raw_offer(*pairs: tuple[str, str]) -> RouterAnswer:
    """An offer the type itself would refuse (empty, 1 or 4 candidates) — built past its validator."""
    return RouterAnswer.model_construct(
        action="offer",
        profile=PROFILE,
        candidates=[Candidate(card_id=c, why=w) for c, w in pairs],
        card_id=None,
        reply=OFFER_REPLY,
        why="людина питає, як продати задум",
        deep_question=None,
    )


class RefusingLlm:
    def __getattr__(self, name: str) -> Any:
        def refuse(*args: Any, **kwargs: Any) -> Any:
            raise AssertionError(f"the model was called ({name}) although route was replaced")

        return refuse


class Recorder:
    """A scripted `route`: gives the answers in order (the last one again when they run out)."""

    def __init__(self, answers: list[RouterAnswer]) -> None:
        self.answers = answers
        self.calls: list[tuple[FacilitationContext, CurrentKnowledge]] = []

    def __call__(self, *args: Any, **kwargs: Any) -> RouterAnswer:
        bound = dict(zip(["ctx", "knowledge", "llm"], args, strict=False)) | kwargs
        self.calls.append((bound["ctx"], bound["knowledge"]))
        return self.answers[min(len(self.calls), len(self.answers)) - 1]


@dataclass
class Run:
    code: int
    out: str
    err: str
    artifacts: dict[str, str] = field(default_factory=dict)

    @property
    def artifact(self) -> str:
        return "\n".join(self.artifacts.values())

    @property
    def everything(self) -> str:
        return "\n".join([self.out, self.err, self.artifact])


def _spike_files() -> dict[Path, float]:
    if not SPIKES.is_dir():
        return {}
    return {p: p.stat().st_mtime for p in SPIKES.iterdir() if p.is_file()}


def run_smoke(monkeypatch: pytest.MonkeyPatch, tmp: Path, fake: Recorder) -> Run:
    before = _spike_files()
    out, err = io.StringIO(), io.StringIO()
    code = 0
    with monkeypatch.context() as m:
        m.setattr(facilitation, "route", fake)
        m.setattr(platform_llm, "make_llm", lambda *a, **k: RefusingLlm())
        for name in ("TMPDIR", "TEMP", "TMP"):
            m.setenv(name, str(tmp))
        m.setattr("tempfile.tempdir", None)
        m.setattr(sys, "argv", [str(SCRIPT)])
        m.chdir(REPO)
        saved_path = list(sys.path)
        try:
            with redirect_stdout(out), redirect_stderr(err):
                runpy.run_path(str(SCRIPT), run_name="__main__")
        except SystemExit as stop:
            code = 0 if stop.code is None else stop.code if isinstance(stop.code, int) else 1
        except Exception as exc:  # an uncaught exception: the process would exit with 1
            err.write(f"\n{type(exc).__name__}: {exc}\n")
            code = 1
        finally:
            sys.path[:] = saved_path
    artifacts: dict[str, str] = {}
    for path, mtime in _spike_files().items():
        if path in before and before[path] == mtime:
            continue
        artifacts[path.name] = path.read_text(encoding="utf-8", errors="replace")
        if path not in before:
            path.unlink()
    return Run(code=code, out=out.getvalue(), err=err.getvalue(), artifacts=artifacts)
