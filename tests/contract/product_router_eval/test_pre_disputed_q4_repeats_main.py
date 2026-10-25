"""Disputed (Q4): how `summary_table` marks that `ot-2` on the 18-card side (`6091f88`) was judged without
`demand-test` in `also_ok` — read as: the table names `demand-test` (the card the mark is about).
Slice tester; from the contract. I4 lives in `test_pre_repeats.py`."""

from pre_helpers import cmp_module


def test_q4_summary_table_marks_ot2_judged_without_demand_test_on_the_18_side() -> None:
    table = cmp_module().summary_table({"ot-2": (5, 5), "wr-1": (5, 5)}, {"ot-2": (5, 5), "wr-1": (4, 5)})
    assert "ot-2" in table
    assert "demand-test" in table
