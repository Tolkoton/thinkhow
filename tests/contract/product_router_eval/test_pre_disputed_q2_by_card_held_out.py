"""Disputed (Q2): the shape of `new.by_card` and `new.held_out` — read as in `router_eval.summary`
(`by_card[card]` has `n`, `first`; `held_out` has `n`, `first`, `offered`).
Slice tester; from the contract."""

from pre_helpers import NEW_CARDS, cmp_module, oc, run_json


def test_q2_new_negative_whose_expect_is_a_new_card_is_not_in_by_card_of_that_card() -> None:
    run = run_json([
        oc("ci-1", True, expect="customer-interviews"),
        oc("ci-2", False, expect="customer-interviews"),
        oc("ci-neg-2", True, kind="negative", expect="customer-interviews"),
    ])  # fmt: skip
    cmp = cmp_module().compare(run, run_json([]), set(), list(NEW_CARDS))
    mine = cmp["new"]["by_card"]["customer-interviews"]
    assert mine["n"] == 2
    assert mine["first"] == 1


def test_q2_held_out_cases_are_counted_apart() -> None:
    run = run_json([
        oc("ci-1", True, expect="customer-interviews"),
        oc("ci-3", False, expect="customer-interviews", offered_ok=True),
        oc("dt-3", True, expect="demand-test"),
        oc("dt-1", False, expect="demand-test", offered_ok=False),
    ])  # fmt: skip
    cmp = cmp_module().compare(run, run_json([]), set(), list(NEW_CARDS))
    held = cmp["new"]["held_out"]
    assert (held["n"], held["first"], held["offered"]) == (2, 1, 2)
