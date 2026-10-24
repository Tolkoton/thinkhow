"""Contract tests of the set of situations `tests/fixtures/routing/cases.yaml`, read through the script's
`load_cases` (slice router-eval, Seam `cases.yaml`, Seam `test_routing_cases.py`, Hardest seam 1;
slice tester, from the contract)."""

import re
from collections import Counter
from pathlib import Path
from typing import Any

import yaml
from rev_fakes import CARDS, CASES, live_normalise, script

KINDS = {"positive", "negative", "tie", "other", "midway"}


def card_ids() -> set[str]:
    return {yaml.safe_load(f.read_text("utf-8"))["id"] for f in CARDS.glob("*.yaml")}


def cases() -> list[dict[str, Any]]:
    loaded: list[dict[str, Any]] = script("router_eval").load_cases(CASES)
    return loaded


def referenced(case: dict[str, Any]) -> list[str]:
    ids = [case["expect"], *case.get("also_ok", []), *case.get("not_first", []), *case.get("absent", [])]
    ids += list(case.get("offered", []))
    if case.get("ended"):
        ids.append(case["ended"]["card_id"])
    return ids


def test_every_card_id_a_case_names_is_a_card_of_cards_dir() -> None:
    known = card_ids()
    assert len(known) == 18
    for case in cases():
        for cid in referenced(case):
            assert cid in known, (case["id"], cid)


def test_every_card_has_three_positive_cases_with_it_as_expect() -> None:
    counts = Counter(c["expect"] for c in cases() if c["kind"] == "positive")
    for cid in card_ids():
        assert counts[cid] >= 3, (cid, counts[cid])


def test_every_card_has_a_negative_case_with_it_in_not_first() -> None:
    negatives = [c for c in cases() if c["kind"] == "negative"]
    for cid in card_ids():
        assert any(cid in c.get("not_first", []) for c in negatives), cid


def test_the_set_has_a_tie_an_other_and_a_midway_case() -> None:
    kinds = Counter(c["kind"] for c in cases())
    assert set(kinds) <= KINDS, kinds
    for kind in ("tie", "other", "midway"):
        assert kinds[kind] >= 1, kind


def test_a_midway_case_after_not_fit_has_that_card_absent() -> None:
    found = [
        c
        for c in cases()
        if c["kind"] == "midway"
        and c["ended"]["end"] == "not_fit"
        and list(c.get("absent", [])) == [c["ended"]["card_id"]]
    ]
    assert found


def test_mid_not_fit_has_five_whys_absent() -> None:
    by_id = {c["id"]: c for c in cases()}
    assert by_id["mid-not-fit"]["ended"] == {"card_id": "five-whys", "end": "not_fit"}
    assert list(by_id["mid-not-fit"]["absent"]) == ["five-whys"]


def test_other_1_has_the_offered_ways_absent_instead_of_expect_not_offered_again() -> None:
    other = {c["id"]: c for c in cases()}["other-1"]
    assert list(other["absent"]) == ["weighted-matrix", "wrap-decision"]
    assert "expect_not_offered_again" not in other


def test_case_ids_are_different() -> None:
    ids = [c["id"] for c in cases()]
    assert len(ids) == len(set(ids))


def test_held_out_part_is_the_third_positive_case_of_each_card() -> None:
    held = [c for c in cases() if c["id"].endswith("-3")]
    assert len(held) == 18
    assert all(c["kind"] == "positive" for c in held)
    assert {c["expect"] for c in held} == card_ids()


def _six_grams(text: str, normalise: Any) -> set[tuple[str, ...]]:
    words = re.findall(r"[\w']+", normalise(text))
    return {tuple(words[i : i + 6]) for i in range(len(words) - 5)}


def _router_items(path: Path) -> list[str]:
    router = yaml.safe_load(path.read_text("utf-8"))["router"]
    items = [router["needs"]]
    for key in ("when_yes", "when_no", "signals"):
        items += list(router[key])
    return items


def test_no_six_words_in_a_row_of_a_case_text_are_in_one_router_item_of_a_card() -> None:
    normalise = live_normalise()
    grams: set[tuple[str, ...]] = set()
    for case in cases():
        grams |= _six_grams(case["text"], normalise)
    assert grams
    for path in sorted(CARDS.glob("*.yaml")):
        for item in _router_items(path):
            hit = _six_grams(item, normalise) & grams
            assert not hit, (path.name, item, hit)
