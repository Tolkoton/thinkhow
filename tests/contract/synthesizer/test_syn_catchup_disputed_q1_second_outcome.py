"""Disputed catch-up test of synthesizer's smoke script (slice tester), question Q1.

«Goal» (2) says «повторний `synthesize` без нових спостережень нічого не пише». A second run that failed
(model error: no run record, Seam step 7) also writes nothing. This file takes the stricter reading — with
Seam 1 («другий — `nothing_new`, жодного виклику моделі») the smoke must see that the second run took
nothing new, not only that it wrote nothing. Not sealed until the slice planner answers Q1.
"""

from pathlib import Path

from syn_catchup_smoke_run import run_smoke


def test_smoke_fails_when_the_second_synthesize_fails_and_writes_nothing(tmp_path: Path) -> None:
    result, seen, _ = run_smoke(tmp_path, "second_failed")
    assert seen["reports"][1]["outcome"] == "failed", seen
    assert seen["writes"][1]["before"] == seen["writes"][1]["after"], seen  # it wrote nothing
    assert result.returncode != 0, result.stdout + result.stderr
