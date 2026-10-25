"""Contract tests of `scripts/router_eval_compare.py` (product-router-eval: Seam, Hardest seam 1, I1, I2).

Slice tester; written from the contract and the skeleton's signatures, not the code. Expected values by hand.
"""

from pathlib import Path
from typing import Any

from pre_helpers import NEW_CARDS, cmp_module, oc, run_json, run_main, side_cell, write_json


def compare(run: list[dict[str, Any]], base: list[dict[str, Any]], old_ids: set[str]) -> dict[str, Any]:
    result: dict[str, Any] = cmp_module().compare(run_json(run), run_json(base), old_ids, list(NEW_CARDS))
    return result


def test_seam1_first_in_base_not_first_now_is_a_regression() -> None:
    cmp = compare(
        [oc("co-1", False), oc("co-2", True)], [oc("co-1", True), oc("co-2", True)], {"co-1", "co-2"}
    )
    assert sorted(cmp["old"]["regressions"]) == ["co-1"]


def test_seam1_not_first_in_base_first_now_is_fixed() -> None:
    cmp = compare(
        [oc("fw-2", True), oc("co-2", True)], [oc("fw-2", False), oc("co-2", True)], {"fw-2", "co-2"}
    )
    assert sorted(cmp["old"]["fixed"]) == ["fw-2"]
    assert cmp["old"]["regressions"] == []


def test_seam1_old_id_absent_from_the_run_is_missing() -> None:
    cmp = compare([oc("co-1", True)], [oc("co-1", True), oc("wr-1", True)], {"co-1", "wr-1"})
    assert sorted(cmp["old"]["missing"]) == ["wr-1"]


def test_seam1_ot2_first_only_by_demand_test_is_changed_expectation() -> None:
    run = [oc("ot-2", True, expect="opportunity-tree", first="demand-test"), oc("co-1", True)]
    base = [oc("ot-2", True, expect="opportunity-tree", first="opportunity-tree"), oc("co-1", True)]
    cmp = compare(run, base, {"ot-2", "co-1"})
    assert "ot-2" in cmp["old"]["changed_expectation"]


def test_unavailable_cases_are_outside_first_now_and_first_base_and_listed_in_unavailable() -> None:
    run = [oc("co-1", True), oc("co-2", action="unavailable"), oc("co-3", True), oc("fw-1", False)]
    base = [oc("co-1", True), oc("co-2", True), oc("co-3", action="unavailable"), oc("fw-1", False)]
    cmp = compare(run, base, {"co-1", "co-2", "co-3", "fw-1"})
    assert cmp["old"]["first_now"] == 1
    assert cmp["old"]["first_base"] == 1
    assert sorted(cmp["old"]["unavailable"]) == ["co-2", "co-3"]


def test_invalid_answer_in_the_run_is_a_miss() -> None:
    cmp = compare(
        [oc("co-1", action="invalid"), oc("co-2", True)],
        [oc("co-1", True), oc("co-2", True)],
        {"co-1", "co-2"},
    )
    assert sorted(cmp["old"]["regressions"]) == ["co-1"]
    assert cmp["old"]["unavailable"] == []


def test_new_unavailable_is_counted_and_kept_out_of_the_new_counters() -> None:
    run = [
        oc("ci-1", True, expect="customer-interviews"),
        oc("ci-2", action="unavailable", expect="customer-interviews"),
        oc("dt-1", False, expect="demand-test", offered_ok=True),
        oc("dt-2", False, expect="demand-test", offered_ok=False),
    ]
    cmp = compare(run, [], set())
    assert cmp["new"]["unavailable"] == 1
    assert cmp["new"]["first"] == 1
    assert cmp["new"]["offered"] == 2


def test_new_negative_broken_by_negative_ok_is_in_negatives_broken() -> None:
    run = [
        oc(
            "ci-neg-1",
            False,
            kind="negative",
            expect="jobs-to-be-done",
            first="customer-interviews",
            negative_ok=False,
        ),
        oc("dt-neg-1", True, kind="negative", expect="opportunity-tree"),
        oc("ci-1", True, expect="customer-interviews"),
        oc("fw-neg-1", False, kind="negative", expect="scamper", negative_ok=False),
    ]
    base = [oc("fw-neg-1", True, kind="negative", expect="scamper")]
    cmp = compare(run, base, {"fw-neg-1"})
    assert sorted(cmp["new"]["negatives_broken"]) == ["ci-neg-1"]


def test_render_has_the_sections_old_cases_and_new_cases() -> None:
    m = cmp_module()
    run = run_json([oc("co-1", False), oc("ci-1", True, expect="customer-interviews")])
    base = run_json([oc("co-1", True)])
    text = m.render(m.compare(run, base, {"co-1"}, list(NEW_CARDS)), run["meta"])
    assert "Старі випадки" in text
    assert "Нові випадки" in text


def test_main_writes_compare_md_beside_the_run_with_the_same_stamp(tmp_path: Path) -> None:
    run = write_json(
        tmp_path / "runs" / "2026-10-26T010203Z.json",
        run_json([oc("co-1", True), oc("ci-1", True, expect="customer-interviews")]),
    )
    base = write_json(
        tmp_path / "base" / "2026-10-25T180821Z.json",
        run_json([oc("co-1", True)], stamp="2026-10-25T180821Z", cards=18),
    )
    done = run_main("--run", str(run), "--base", str(base))
    assert done.returncode == 0, done.stdout + done.stderr
    out = tmp_path / "runs" / "2026-10-26T010203Z.compare.md"
    assert out.is_file(), sorted(p.name for p in (tmp_path / "runs").iterdir())
    text = out.read_text(encoding="utf-8")
    assert "Старі випадки" in text and "Нові випадки" in text
    assert not (tmp_path / "base" / "2026-10-25T180821Z.compare.md").exists()


def test_main_carries_absent_broken_of_the_run_into_compare_md(tmp_path: Path) -> None:
    outcomes = [
        oc("co-1", True),
        oc("mid-not-fit", True, kind="midway", expect="issue-tree", absent_ok=False),
    ]
    run = write_json(tmp_path / "2026-10-26T010203Z.json", run_json(outcomes, absent_broken=["mid-not-fit"]))
    base = write_json(
        tmp_path / "base.json",
        run_json([oc("co-1", True), oc("mid-not-fit", True, kind="midway", expect="issue-tree")]),
    )
    done = run_main("--run", str(run), "--base", str(base))
    assert done.returncode == 0, done.stdout + done.stderr
    assert "mid-not-fit" in (tmp_path / "2026-10-26T010203Z.compare.md").read_text(encoding="utf-8")


def test_shares_counts_first_over_the_runs_that_graded_the_case() -> None:
    runs = [
        run_json([oc("wr-1", True), oc("fw-2", True)]),
        run_json([oc("wr-1", False), oc("fw-2", True)]),
        run_json([oc("wr-1", action="unavailable"), oc("fw-2", True)]),
    ]
    got = {k: tuple(v) for k, v in cmp_module().shares(runs).items()}
    assert got == {"wr-1": (1, 2), "fw-2": (3, 3)}


def test_summary_table_shows_x_z_n_of_each_side_in_its_own_column() -> None:
    table = cmp_module().summary_table({"wr-1": (5, 5), "fw-2": (3, 5)}, {"wr-1": (4, 5), "fw-2": (3, 4)})
    assert "5 з 5" in side_cell(table, "wr-1", "18")
    assert "4 з 5" in side_cell(table, "wr-1", "25")
    assert "3 з 5" in side_cell(table, "fw-2", "18")
    assert "3 з 4" in side_cell(table, "fw-2", "25")


def test_I1_every_run_case_goes_to_exactly_one_part_old_by_old_ids_else_new() -> None:
    # Input 1: new ids that look like old ones; two old ids absent from the run.
    run = [
        oc("co-1", False),
        oc("co-2", True),
        oc("co-10", True, expect="positioning"),
        oc("ot-2-new", True, expect="demand-test"),
        oc("ci-1", False, expect="customer-interviews", offered_ok=True),
    ]
    base = [
        oc("co-1", True),
        oc("co-2", False),
        oc("ot-2", True, expect="opportunity-tree"),
        oc("fw-2", False),
    ]
    cmp = compare(run, base, {"co-1", "co-2", "ot-2", "fw-2"})
    old = cmp["old"]
    assert sorted(old["regressions"]) == ["co-1"]
    assert sorted(old["fixed"]) == ["co-2"]
    assert sorted(old["missing"]) == ["fw-2", "ot-2"]
    in_old = set(old["regressions"]) | set(old["fixed"]) | set(old["missing"]) | set(old["unavailable"])
    assert not in_old & {"co-10", "ot-2-new", "ci-1"}
    assert cmp["new"]["first"] == 2
    assert cmp["new"]["offered"] == 3

    # Input 2: the empty set of old ids — nothing is old, nothing is missing.
    cmp = compare(run, base, set())
    assert cmp["old"]["regressions"] == []
    assert cmp["old"]["fixed"] == []
    assert cmp["old"]["missing"] == []


def test_I2_regressions_and_fixed_are_per_case_never_without_base_never_unavailable() -> None:
    base = [
        oc("a-1", True), oc("b-1", False), oc("c-1", True), oc("d-1", True),
        oc("e-1", action="unavailable"), oc("g-1", False), oc("z-1", True),
    ]  # fmt: skip
    run = [
        oc("a-1", False), oc("b-1", True), oc("c-1", True), oc("d-1", action="unavailable"),
        oc("e-1", True), oc("g-1", False), oc("h-1", True),
    ]  # fmt: skip
    ids = {"a-1", "b-1", "c-1", "d-1", "e-1", "g-1", "h-1", "z-1"}
    cmp = compare(run, base, ids)
    assert sorted(cmp["old"]["regressions"]) == ["a-1"]
    assert sorted(cmp["old"]["fixed"]) == ["b-1"]

    # The same two runs the other way round: a different set of case_ids on each side.
    cmp = compare(base, run, ids)
    assert sorted(cmp["old"]["regressions"]) == ["b-1"]
    assert sorted(cmp["old"]["fixed"]) == ["a-1"]

    # Two equal runs: nothing changed.
    cmp = compare(run, run, ids)
    assert cmp["old"]["regressions"] == []
    assert cmp["old"]["fixed"] == []
