"""Catch-up contract tests of skel-knowledge: the smoke script (slice tester).

Written from the contract (.engine/slices/skel-knowledge.md, «Exit criterion»), not the code. The
script is run the way the exit criterion names it — `python scripts/smoke_test_skel_knowledge.py` from
the repository root — and judged by its exit code, its stdout and what it leaves in the repository.
"""

import os
import subprocess
import sys
from pathlib import Path

import yaml

from thinkhow.knowledge import Card, card_prompt

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "scripts" / "smoke_test_skel_knowledge.py"
SKIP_DIRS = {".git", ".venv", "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache", "node_modules"}
POC_PHASES = [
    "phase_1_time_travel",
    "phase_2_blind_spots",
    "phase_3_triage",
    "phase_4_mitigation_tripwires",
]


def run_smoke(tmp: Path) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ, TMPDIR=str(tmp), TEMP=str(tmp), TMP=str(tmp))
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
    )


def change_records_in_repo() -> set[Path]:
    found: set[Path] = set()
    for root, dirs, files in os.walk(REPO):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        here = Path(root)
        if here.name == "changes" and here.parent.name == "knowledge":
            found.update(here / f for f in files)
    return found


def test_smoke_succeeds_and_prints_the_card_prompt_of_the_real_card(tmp_path: Path) -> None:
    result = run_smoke(tmp_path)
    assert result.returncode == 0, result.stderr
    card = Card.model_validate(
        yaml.safe_load((REPO / "cards" / "pre-mortem.yaml").read_text(encoding="utf-8"))
    )
    assert card_prompt(card) in result.stdout
    for phase_id in POC_PHASES:
        assert phase_id in result.stdout


def test_smoke_seeds_in_a_temporary_folder_not_in_the_repository(tmp_path: Path) -> None:
    before = change_records_in_repo()
    result = run_smoke(tmp_path)
    assert result.returncode == 0, result.stderr
    assert change_records_in_repo() == before
