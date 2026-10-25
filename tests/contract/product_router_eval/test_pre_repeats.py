"""Contract test of I4 (product-router-eval): `main --repeats18 <dir> --repeats25 <dir>` counts each
repeat run on the side of the folder it was read from, once. Slice tester; from the contract, not the code.

Where `summary.md` lands is not pinned: the contract names `repeats/summary.md` and the two folders
`repeats/18/`, `repeats/25/`, so both the common parent of the given folders and the real
`.engine/artifacts/router-eval/repeats/summary.md` are accepted; the real file is restored afterwards.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from pre_helpers import ARTIFACTS, oc, run_json, run_main, side_cell, write_json

REAL_SUMMARY = ARTIFACTS / "router-eval" / "repeats" / "summary.md"


@pytest.fixture
def real_summary_before() -> Iterator[bytes | None]:
    before = REAL_SUMMARY.read_bytes() if REAL_SUMMARY.exists() else None
    yield before
    if before is None:
        REAL_SUMMARY.unlink(missing_ok=True)
    else:
        REAL_SUMMARY.write_bytes(before)


def _run(folder: Path, stamp: str, wr1: dict[str, object], fw2: dict[str, object], cards: int) -> None:
    write_json(folder / f"{stamp}.json", run_json([wr1, fw2], stamp=stamp, cards=cards))
    (folder / f"{stamp}.md").write_text(f"# Router eval {stamp}\n", encoding="utf-8")


def test_I4_each_repeat_run_counts_once_on_the_side_of_the_folder_it_was_read_from(
    tmp_path: Path, real_summary_before: bytes | None
) -> None:
    d18, d25 = tmp_path / "repeats" / "18", tmp_path / "repeats" / "25"
    # The same case_ids on both sides; `meta.cards` lies on purpose (25 in the 18 folder, 18 in the 25
    # folder); the file names of the two folders interleave in time; a run on the 25 side is unavailable.
    _run(d18, "2026-10-26T000002Z", oc("wr-1", True), oc("fw-2", True), cards=25)
    _run(d18, "2026-10-26T000004Z", oc("wr-1", True), oc("fw-2", False), cards=25)
    _run(d25, "2026-10-26T000001Z", oc("wr-1", True), oc("fw-2", True), cards=18)
    _run(d25, "2026-10-26T000003Z", oc("wr-1", False), oc("fw-2", True), cards=18)
    _run(d25, "2026-10-26T000005Z", oc("wr-1", False), oc("fw-2", True), cards=18)
    _run(
        d25,
        "2026-10-26T000006Z",
        oc("wr-1", action="unavailable"),
        oc("fw-2", action="unavailable"),
        cards=18,
    )
    done = run_main("--repeats18", str(d18), "--repeats25", str(d25))
    assert done.returncode == 0, done.stdout + done.stderr
    beside = tmp_path / "repeats" / "summary.md"
    if beside.is_file():
        table = beside.read_text(encoding="utf-8")
    else:
        assert REAL_SUMMARY.is_file(), "no summary.md beside the folders nor in repeats/"
        assert REAL_SUMMARY.read_bytes() != real_summary_before, "repeats/summary.md was not written"
        table = REAL_SUMMARY.read_text(encoding="utf-8")
    assert "2 з 2" in side_cell(table, "wr-1", "18")
    assert "1 з 3" in side_cell(table, "wr-1", "25")
    assert "1 з 2" in side_cell(table, "fw-2", "18")
    assert "3 з 3" in side_cell(table, "fw-2", "25")
