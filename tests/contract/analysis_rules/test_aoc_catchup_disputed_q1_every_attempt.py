"""Disputed (Q1) catch-up test of `scripts/analyze_owner_conversation.py`: the artifact keeps the raw JSON
of every attempt, an earlier one included. Slice tester; from the contract. Not sealed before the slice
planner answers Q1.
"""

import pytest
from aoc_fakes import PlanLlm, guard_artifact, run_main

__all__ = ["guard_artifact"]


@pytest.mark.usefixtures("guard_artifact")
def test_artifact_keeps_the_raw_json_of_an_earlier_attempt(monkeypatch: pytest.MonkeyPatch) -> None:
    run_main(monkeypatch, PlanLlm(marker="СПРОБА-ПЕРША", old_marker="СТАРИЙ-ПЕРША"), attempt=1)
    _, text = run_main(monkeypatch, PlanLlm(marker="СПРОБА-ДРУГА", old_marker="СТАРИЙ-ДРУГА"), attempt=2)
    for marker in ("СПРОБА-ПЕРША", "СТАРИЙ-ПЕРША", "СПРОБА-ДРУГА", "СТАРИЙ-ДРУГА"):
        assert f'"{marker}-' in text, f"no raw JSON of {marker}"
