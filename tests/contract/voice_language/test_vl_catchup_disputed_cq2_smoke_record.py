"""Catch-up test of voice-language (slice tester): the smoke's output, under the answer to question CQ2.

CQ2: «Вивід — `.engine/artifacts/spikes/voice-language-smoke-<дата>.txt`» (Exit criterion). The slice planner
answered with the other reading (ledger, 2026-10-23T17:10:28Z): the line names where the smoke's printed
output is kept; the script prints, the builder saves its stdout there, and a smoke writing into the
repository would break «в тимчасовій теці». So a run of the script prints its output and writes no record
itself.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from vl_catchup_smoke_run import run_smoke, server_ran


def test_smoke_prints_its_output_and_writes_no_record_itself(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    run = run_smoke(monkeypatch, tmp_path)
    assert run.ok, run.out
    server_ran(run)
    assert run.out.strip(), "the smoke printed nothing: there is no output for the record"
    assert run.written == {}, f"the smoke itself wrote its record into the repository: {sorted(run.written)}"
