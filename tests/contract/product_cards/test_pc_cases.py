"""Contract tests of product-cards: the cases of the 7 new cards in `tests/fixtures/routing/cases.yaml`
(Seam «Cases», Hardest seam 3). Slice tester; written from the contract, not the code."""

import re

from pc_helpers import NEW_IDS, OLD_IDS, PREFIX, cases, old_cases

PAIRS = [
    ("customer-interviews", "jobs-to-be-done"),
    ("demand-test", "opportunity-tree"),
    ("offer-design", "value-pricing"),
    ("offer-design", "positioning"),
    ("value-pricing", "positioning"),
    ("traction-channels", "demand-test"),
]


def test_each_prefix_has_positive_1_to_3_and_negatives_named_neg_1_or_2() -> None:
    by_id = {c["id"]: c for c in cases()}
    for prefix, cid in PREFIX.items():
        for n in (1, 2, 3):
            case = by_id.get(f"{prefix}-{n}")
            assert case is not None, f"{prefix}-{n} is missing"
            assert (case["kind"], case["expect"]) == ("positive", cid), case["id"]
        negs = [k for k in by_id if k.startswith(f"{prefix}-neg-")]
        assert negs, f"no {prefix}-neg-N"
        for k in negs:
            assert re.fullmatch(rf"{re.escape(prefix)}-neg-[12]", k), k
            assert by_id[k]["kind"] == "negative", k
    for case in cases():
        if case["id"].endswith("-3"):
            assert case["kind"] == "positive", case["id"]


def test_a_hard_negative_has_a_new_card_as_expect_and_an_old_one_in_not_first() -> None:
    old = {c["id"] for c in old_cases()}
    found = [
        c["id"]
        for c in cases()
        if c["id"] not in old
        and c["kind"] == "negative"
        and c["expect"] in NEW_IDS
        and set(c.get("not_first", [])) & set(OLD_IDS)
    ]
    assert found


def test_seam3_each_pair_has_a_negative_case_one_side_expect_the_other_in_not_first() -> None:
    negatives = [c for c in cases() if c["kind"] == "negative"]
    for a, b in PAIRS:
        assert any(
            (c["expect"] == a and b in c.get("not_first", []))
            or (c["expect"] == b and a in c.get("not_first", []))
            for c in negatives
        ), (a, b)


def test_ue_neg_1_is_the_hard_negative_between_unit_economics_and_weighted_matrix() -> None:
    case = {c["id"]: c for c in cases()}.get("ue-neg-1")
    assert case is not None, "ue-neg-1 is missing"
    assert case["kind"] == "negative"
    sides = {case["expect"], *case.get("not_first", [])}
    assert {"unit-economics", "weighted-matrix"} <= sides, case
