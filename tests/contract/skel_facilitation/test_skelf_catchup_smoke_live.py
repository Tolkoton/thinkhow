"""Catch-up contract test of skel-facilitation: the smoke script against the real Vertex (`-m live`).

Slice tester; written from the contract («Exit criterion»), not the code. The script is run the way the
exit criterion names it, from the repository root, and judged by its exit code and its stdout.
"""

import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "scripts" / "smoke_test_skel_facilitation.py"
PHASES = [
    "phase_1_time_travel",
    "phase_2_blind_spots",
    "phase_3_triage",
    "phase_4_mitigation_tripwires",
]


@pytest.mark.live
def test_smoke_against_real_vertex_succeeds_and_prints_a_phase_of_the_card() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=REPO,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=300,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert any(phase in result.stdout for phase in PHASES), result.stdout
