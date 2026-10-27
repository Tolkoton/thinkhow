"""Catch-up contract tests of knowledge-versions: the smoke script (slice tester).

Written from the contract (.engine/slices/knowledge-versions.md, «Goal» (2) and «Exit criterion»), not from
the script. The exit criterion says the script «друкує й перевіряє» each value: so it must exit 0 on the real
code and exit non-zero when one of the values it checks is wrong. Each breakage below damages one value only.
"""

from pathlib import Path
from typing import Any

import pytest
from kv_catchup_smoke_run import keep_artifact, run_smoke

CARDS_IN_REPO = 25


@pytest.fixture(scope="module")
def clean_run(tmp_path_factory: pytest.TempPathFactory) -> tuple[Any, dict[str, Any]]:
    with keep_artifact():
        return run_smoke(tmp_path_factory.mktemp("kv_smoke_clean"))


def test_smoke_runs_from_the_repository_root_and_exits_0(clean_run: tuple[Any, dict[str, Any]]) -> None:
    result, seen = clean_run
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip(), "the script prints what it checks"
    assert seen["apply_calls"] >= 1 and seen["rollback_calls"] >= 1, seen


def test_smoke_runs_on_a_local_storage_seeded_with_the_25_cards(
    clean_run: tuple[Any, dict[str, Any]],
) -> None:
    result, seen = clean_run
    assert result.returncode == 0, result.stdout + result.stderr
    assert len(list((Path(__file__).resolve().parents[3] / "cards").glob("*.yaml"))) == CARDS_IN_REPO
    assert seen["local"] is True, seen
    assert seen["cards_before_change"] == CARDS_IN_REPO, seen


def test_smoke_checks_the_change_with_the_real_measure(clean_run: tuple[Any, dict[str, Any]]) -> None:
    result, seen = clean_run
    assert result.returncode == 0, result.stdout + result.stderr
    assert seen["measure_is_real"] is True, seen


def test_smoke_fails_when_the_record_is_not_in_current_memory_after_the_change(tmp_path: Path) -> None:
    with keep_artifact():
        result, seen = run_smoke(tmp_path, "record_removed")
    assert seen.get("removed_by") is not None, seen  # the breakage took place
    assert result.returncode != 0, result.stdout + result.stderr


def test_smoke_fails_when_the_record_is_back_after_the_rollback(tmp_path: Path) -> None:
    with keep_artifact():
        result, seen = run_smoke(tmp_path, "record_back")
    assert seen.get("re_applied") is not None, seen
    assert seen.get("n_after") == 1, seen  # n is right: only the record is wrong
    assert result.returncode != 0, result.stdout + result.stderr


def test_smoke_fails_when_n_after_the_rollback_is_not_1(tmp_path: Path) -> None:
    with keep_artifact():
        result, seen = run_smoke(tmp_path, "second_rollback")
    assert seen.get("second") is True, seen
    assert seen.get("n_after") == 2, seen
    assert result.returncode != 0, result.stdout + result.stderr


def test_smoke_fails_when_a_card_file_changes_its_bytes(tmp_path: Path) -> None:
    with keep_artifact():
        result, seen = run_smoke(tmp_path, "card_bytes")
    assert seen.get("card_touched"), seen
    assert result.returncode != 0, result.stdout + result.stderr
