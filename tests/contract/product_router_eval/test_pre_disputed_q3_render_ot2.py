"""Disputed (Q3): how `render` says that `ot-2` is first only thanks to `demand-test` — read as: the
rendered text names both `ot-2` and `demand-test`. Slice tester; from the contract."""

from pre_helpers import NEW_CARDS, cmp_module, oc, run_json


def test_q3_render_names_ot2_first_only_by_demand_test() -> None:
    m = cmp_module()
    run = run_json([oc("ot-2", True, expect="opportunity-tree", first="demand-test"), oc("co-1", True)])
    base = run_json([oc("ot-2", True, expect="opportunity-tree", first="opportunity-tree"), oc("co-1", True)])
    text = m.render(m.compare(run, base, {"ot-2", "co-1"}, list(NEW_CARDS)), run["meta"])
    assert "ot-2" in text
    assert "demand-test" in text
