"""Test gap (overseer, task 723) of `scripts/smoke_test_learning_loop.py`, the step «a second synthesize».

Seam 1 of .engine/slices/synthesizer.md: the second run is `nothing_new`, with no model call. A second run
that re-fed the old observations to the model and was refused writes no revision; if it also leaves no run
record, the checks «no second run record» and «no revision» pass, and so does a line like
`runs(storage)[-1].considered != []` (true from the first run's record). Only the second run's outcome tells.

The breakage is put in front of the sealed bootstrap (syn_catchup_smoke_run.BOOT): on the second call of
the real `synthesize`, `_new` hands back every observation (the old ones re-fed), the model is really called,
`_apply` refuses without writing, and the run record is not written. The smoke must exit non-zero.
"""

import json
from pathlib import Path

import pytest
import syn_catchup_smoke_run
from syn_catchup_smoke_run import run_smoke

REFED = r"""
import json as _json
import os as _os
from pathlib import Path as _Path

import thinkhow.learning.synthesize as _S

_GAP = _Path(_os.environ["SYN_GAP_RECORD"])
_gap = {"new_calls": 0, "refed": 0, "model_answered": False, "run_record_skipped": False}
_real_new, _real_write_run, _real_apply = _S._new, _S._write_run, _S._apply


def _gap_save():
    _GAP.write_text(_json.dumps(_gap), encoding="utf-8")


def _new(observations, feed, done):
    _gap["new_calls"] += 1
    if _gap["new_calls"] == 2:
        _gap["refed"] = len(observations)
        _gap_save()
        return list(observations)
    return _real_new(observations, feed, done)


def _apply(storage, change, vet, measure):
    if _gap["new_calls"] == 2:
        _gap["model_answered"] = True
        _gap_save()
        return "rejected", None, "re-fed observations"
    return _real_apply(storage, change, vet, measure)


def _write_run(storage, run):
    if _gap["new_calls"] == 2:
        _gap["run_record_skipped"] = True
        _gap_save()
        return None
    return _real_write_run(storage, run)


_S._new, _S._apply, _S._write_run = _new, _apply, _write_run
_gap_save()
"""


def test_smoke_fails_when_the_second_synthesize_refeeds_and_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gap = tmp_path / "gap.json"
    monkeypatch.setenv("SYN_GAP_RECORD", str(gap))
    monkeypatch.setattr(syn_catchup_smoke_run, "BOOT", REFED + syn_catchup_smoke_run.BOOT)
    result, seen, _ = run_smoke(tmp_path)
    told = json.loads(gap.read_text(encoding="utf-8"))
    assert told["refed"] > 0 and told["model_answered"] and told["run_record_skipped"], told
    assert [r["outcome"] for r in seen["reports"]] == ["applied", "rejected"], seen
    assert seen["writes"][1]["before"] == seen["writes"][1]["after"], seen  # it wrote nothing
    assert result.returncode != 0, result.stdout + result.stderr
    assert "a second synthesize took nothing new: rejected" in result.stdout, result.stdout
