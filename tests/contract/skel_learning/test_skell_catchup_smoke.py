"""Catch-up contract tests of skel-learning: the smoke script (slice tester).

Written from the contract (.engine/slices/skel-learning.md, «Exit criterion»), not the code. The script
is run the way the exit criterion names it — `python scripts/smoke_test_skel_learning.py` from the
repository root — and judged by its exit code, its stdout and what it leaves in the repository.

Corrected by objection (round 2, slice continuous-analysis, task 202): the observation carries
`first_turn`/`last_turn` (1, 2) instead of `session_no`.

Carried over by objection (task 720, answer A) to analysis-rules: the printed
file is an `ObservationSet`; the local script's answer is one `progress` observation.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

from pydantic import ValidationError

from thinkhow.learning.observations import ObservationSet

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "scripts" / "smoke_test_skel_learning.py"
SKIP_DIRS = {".git", ".venv", "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache", "node_modules"}
LOCAL_FINDING = "(локальний режим) Людина назвала план; фасилітатор поставив одне питання."


def run_smoke(tmp: Path) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ, TMPDIR=str(tmp), TEMP=str(tmp), TMP=str(tmp))
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=300,
    )


def printed_sets(out: str) -> list[ObservationSet]:
    """Every JSON object in `out` that is an ObservationSet (pretty-printed or on one line)."""
    decoder = json.JSONDecoder()
    found: list[ObservationSet] = []
    i = out.find("{")
    while i != -1:
        try:
            value, end = decoder.raw_decode(out, i)
        except json.JSONDecodeError:
            i = out.find("{", i + 1)
            continue
        if isinstance(value, dict):
            try:
                found.append(ObservationSet.model_validate(value))
            except ValidationError:
                pass
        i = out.find("{", end)
    return found


def traces_in_repo() -> set[Path]:
    """Files the chain would leave if it ran in the repository: observations and conversations."""
    found: set[Path] = set()
    for root, dirs, files in os.walk(REPO):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        here = Path(root)
        for name in files:
            if name == "conversation.md" or "observations" in here.parts:
                found.add(here / name)
    return found


def test_smoke_succeeds_and_prints_the_observation_file_with_a_link_to_a_turn_of_the_two_turn_topic(
    tmp_path: Path,
) -> None:
    result = run_smoke(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    sets = printed_sets(result.stdout)
    assert sets, result.stdout
    got = sets[0]
    assert got.uid == "local-owner"
    assert (got.first_turn, got.last_turn) == (1, 2)
    assert got.observations, result.stdout
    for obs in got.observations:
        assert obs.turn in {1, 2}
        assert obs.link == f"/topics/local-owner/{got.topic_id}#t{obs.turn}"
        assert re.fullmatch(r"/topics/local-owner/[^/#]+#t[12]", obs.link)


def test_smoke_observation_is_the_local_scripted_answer(tmp_path: Path) -> None:
    result = run_smoke(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    sets = printed_sets(result.stdout)
    assert sets, result.stdout
    assert len(sets[0].observations) == 1, result.stdout
    obs = sets[0].observations[0]
    assert obs.kind == "progress"
    assert obs.finding == LOCAL_FINDING
    assert obs.worked is True
    assert obs.cause == "facilitation"


def test_smoke_runs_in_a_temporary_folder_and_leaves_nothing_in_the_repository(tmp_path: Path) -> None:
    before = traces_in_repo()
    result = run_smoke(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert traces_in_repo() == before
