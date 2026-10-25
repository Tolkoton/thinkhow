"""Disputed catch-up tests of product-cards (question Q2): must the smoke itself refuse an `offer` whose
candidate list is empty, of one, or of four — answers the `RouterAnswer` type already refuses, so the real
`route` cannot return them? This file takes the reading that it must («код 0 лише тоді, коли дія `offer`
з 2–3 кандидатами … порожній список … — код 1»); the answers are built past the type's validator.
Slice tester; written from the contract, not the code.
"""

from pathlib import Path

import pytest
from pc_smoke_fakes import WHY_DT, WHY_JTBD, Recorder, raw_offer, run_smoke


def test_q2_smoke_exits_1_on_an_offer_with_an_empty_list(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    run = run_smoke(monkeypatch, tmp_path, Recorder([raw_offer()]))
    assert run.code == 1, run.everything


def test_q2_smoke_exits_1_on_an_offer_of_1_or_4_candidates(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    one = raw_offer(("demand-test", WHY_DT))
    four = raw_offer(
        ("demand-test", WHY_DT),
        ("jobs-to-be-done", WHY_JTBD),
        ("pre-mortem", "що може зламатися"),
        ("positioning", "чим відрізняється"),
    )
    for answer in (one, four):
        run = run_smoke(monkeypatch, tmp_path, Recorder([answer]))
        assert run.code == 1, f"{len(answer.candidates)} candidates gave {run.code}:\n{run.everything}"
