"""Catch-up contract tests of notes-readers: the smoke script (slice tester).

Written from the contract (.engine/slices/notes-readers.md, «Goal» (2) and «Exit criterion»), not from the
script. The script must exit 0 on the real code, build the instructions on the 25 real cards with the two
notes «Goal» (2) names, write its output to the artifact, and exit non-zero when what it shows is wrong.
Each breakage below damages one thing only (nr_catchup_smoke_run.BOOT).
"""

from pathlib import Path
from typing import Any

import pytest
from nr_catchup_smoke_run import real_card_ids, run_smoke

Run = tuple[Any, dict[str, Any], str | None]


@pytest.fixture(scope="module")
def clean_run(tmp_path_factory: pytest.TempPathFactory) -> Run:
    return run_smoke(tmp_path_factory.mktemp("nr_smoke_clean"))


def _two_notes(memory: list[dict[str, Any]]) -> bool:
    shape = sorted((r["audience"], tuple(r["cards"])) for r in memory)
    return shape == [("facilitator", ("five-whys",)), ("router", ("pre-mortem",))]


def test_smoke_builds_the_router_instruction_on_the_25_real_cards_and_two_notes_and_exits_0(
    clean_run: Run,
) -> None:
    result, seen, _ = clean_run
    assert result.returncode == 0, result.stdout + result.stderr
    ids = real_card_ids()
    assert len(ids) == 25, ids
    with_notes = [c for c in seen["router_calls"] if _two_notes(c["memory"])]
    assert with_notes, seen["router_calls"]
    assert all(c["cards"] == ids for c in with_notes), (ids, with_notes)


def test_smoke_builds_the_facilitator_instruction_of_five_whys_and_of_pre_mortem(clean_run: Run) -> None:
    result, seen, _ = clean_run
    assert result.returncode == 0, result.stdout + result.stderr
    cards = {c["card"] for c in seen["system_calls"] if _two_notes(c["memory"])}
    assert {"five-whys", "pre-mortem"} <= cards, seen["system_calls"]


def test_smoke_writes_its_output_to_the_artifact(clean_run: Run) -> None:
    result, _, artifact = clean_run
    assert result.returncode == 0, result.stdout + result.stderr
    assert artifact is not None, "no .engine/artifacts/notes-readers/smoke.txt"
    lines = [line for line in result.stdout.splitlines() if line.strip() and not line.startswith("{")]
    assert lines, "the script prints what it shows"
    assert all(line in artifact for line in lines), (result.stdout, artifact)


def test_smoke_fails_when_the_router_note_stands_in_another_card_section(tmp_path: Path) -> None:
    result, seen, _ = run_smoke(tmp_path, "router_note_elsewhere")
    assert seen["broken"], seen  # the breakage took place
    assert result.returncode != 0, result.stdout + result.stderr


def test_smoke_fails_when_the_router_note_is_missing_from_pre_mortem(tmp_path: Path) -> None:
    result, seen, _ = run_smoke(tmp_path, "router_note_missing")
    assert seen["broken"], seen
    assert result.returncode != 0, result.stdout + result.stderr


def test_smoke_fails_when_the_facilitator_of_five_whys_has_no_note(tmp_path: Path) -> None:
    result, seen, _ = run_smoke(tmp_path, "facilitator_note_missing")
    assert any(b[1] == "five-whys" for b in seen["broken"]), seen
    assert result.returncode != 0, result.stdout + result.stderr


def test_smoke_fails_when_the_facilitator_of_pre_mortem_has_the_five_whys_note(tmp_path: Path) -> None:
    result, seen, _ = run_smoke(tmp_path, "facilitator_note_leaks")
    assert any(b[1] == "pre-mortem" for b in seen["broken"]), seen
    assert result.returncode != 0, result.stdout + result.stderr
