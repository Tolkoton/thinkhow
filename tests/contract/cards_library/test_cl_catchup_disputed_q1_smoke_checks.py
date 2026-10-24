"""Disputed catch-up test of cards-library (question Q1): does the smoke script itself check the results
the exit criterion lists («`current` — 18 карток»), or only show them? This file takes the stricter
reading: a smoke whose Job publishes another number of cards must fail. Slice tester; from the contract.

The script runs from a copy of the repository (`src/`, `scripts/`, `cards/`) whose `cards/` is changed;
the Job's cards folder is `job.py` `CARDS_DIR`, the repository's `cards/` (contract, «Exit criterion»), so
in the copy it is the copy's `cards/`. PYTHONPATH points at the copy's `src/`.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[3]
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", ".mypy_cache", ".ruff_cache")


def make_copy(dest: Path) -> Path:
    for name in ("src", "scripts", "cards"):
        shutil.copytree(REPO / name, dest / name, ignore=IGNORE)
    return dest


def run_copy(copy: Path, tmp: Path) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ, TMPDIR=str(tmp), TEMP=str(tmp), TMP=str(tmp), PYTHONPATH=str(copy / "src"))
    return subprocess.run(
        [sys.executable, str(copy / "scripts" / "smoke_test_cards_library.py")],
        cwd=copy,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=300,
    )


def test_q1_smoke_fails_when_the_job_publishes_17_or_19_cards_instead_of_18(tmp_path: Path) -> None:
    work = tmp_path / "tmp"
    work.mkdir()

    intact = make_copy(tmp_path / "intact")
    sane = run_copy(intact, work)
    assert sane.returncode == 0, f"the smoke fails in an unchanged copy:\n{sane.stdout}\n{sane.stderr}"

    fewer = make_copy(tmp_path / "fewer")
    (fewer / "cards" / "scamper.yaml").unlink()
    assert run_copy(fewer, work).returncode != 0, "17 cards published and the smoke still exited 0"

    more = make_copy(tmp_path / "more")
    extra = yaml.safe_load((more / "cards" / "scamper.yaml").read_text(encoding="utf-8"))
    extra["id"] = "scamper-extra"
    (more / "cards" / "scamper-extra.yaml").write_text(
        yaml.safe_dump(extra, allow_unicode=True), encoding="utf-8"
    )
    assert run_copy(more, work).returncode != 0, "19 cards published and the smoke still exited 0"
