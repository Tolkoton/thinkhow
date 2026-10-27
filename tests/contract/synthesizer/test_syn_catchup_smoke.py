"""Catch-up contract tests of synthesizer: the smoke script (slice tester).

Written from the contract (.engine/slices/synthesizer.md, «Goal» (2), Seam 5 and «Exit criterion»), not from
the script. The script must exit 0 on the real code, go through the real Job and the real app, write its
output to the artifact, and exit non-zero when one of the values «Goal» (2) names is wrong. Each breakage
below damages one value only (syn_catchup_smoke_run.BOOT).
"""

from pathlib import Path
from typing import Any

import pytest
from syn_catchup_smoke_run import run_smoke

Run = tuple[Any, dict[str, Any], str | None]


@pytest.fixture(scope="module")
def clean_run(tmp_path_factory: pytest.TempPathFactory) -> Run:
    return run_smoke(tmp_path_factory.mktemp("syn_smoke_clean"))


def test_smoke_goes_through_the_real_job_and_the_real_app_and_exits_0(clean_run: Run) -> None:
    result, seen, _ = clean_run
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip(), "the script prints what it checks"
    assert seen["analyze_calls"] >= 1, seen  # job.run(["analyze"])
    assert seen["synthesize_calls"] == 2, seen  # job.run(["synthesize"]) twice: the change, then the repeat
    assert seen["rollback_calls"] == 1, seen  # «Відкотити» through the app's route
    assert seen["local"] is True, seen


def test_smoke_writes_its_output_to_the_artifact(clean_run: Run) -> None:
    result, _, artifact = clean_run
    assert result.returncode == 0, result.stdout + result.stderr
    assert artifact is not None, "no .engine/artifacts/synthesizer/smoke.txt"
    # the script's own lines; the JSON lines of the structured log are the app's, not the script's output
    lines = [line for line in result.stdout.splitlines() if line.strip() and not line.startswith("{")]
    assert lines and all(line in artifact for line in lines), (result.stdout, artifact)


def test_smoke_fails_when_synthesize_writes_no_new_revision(tmp_path: Path) -> None:
    result, seen, _ = run_smoke(tmp_path, "first_nothing")
    assert seen["reports"][0]["outcome"] == "nothing_new", seen  # the breakage took place
    assert result.returncode != 0, result.stdout + result.stderr


def test_smoke_fails_when_the_observation_link_is_not_a_link_into_the_topic(tmp_path: Path) -> None:
    result, seen, _ = run_smoke(tmp_path, "link_elsewhere")
    assert seen.get("link_broken") is True, seen
    assert result.returncode != 0, result.stdout + result.stderr


def test_smoke_fails_when_the_note_is_still_in_memory_after_the_rollback(tmp_path: Path) -> None:
    result, seen, _ = run_smoke(tmp_path, "rollback_keeps")
    assert seen.get("re_applied") is not None, seen
    assert result.returncode != 0, result.stdout + result.stderr


def test_smoke_fails_when_the_second_synthesize_writes_a_run_record(tmp_path: Path) -> None:
    result, seen, _ = run_smoke(tmp_path, "second_run_record")
    assert seen.get("extra_run") is True, seen
    assert result.returncode != 0, result.stdout + result.stderr


def test_smoke_fails_when_the_second_synthesize_writes_a_revision(tmp_path: Path) -> None:
    result, seen, _ = run_smoke(tmp_path, "second_revision")
    assert seen.get("extra_rev") is not None, seen
    assert result.returncode != 0, result.stdout + result.stderr


def test_smoke_fails_when_a_card_file_changes_its_bytes(tmp_path: Path) -> None:
    result, seen, _ = run_smoke(tmp_path, "card_bytes")
    assert seen.get("card_touched"), seen
    assert result.returncode != 0, result.stdout + result.stderr
