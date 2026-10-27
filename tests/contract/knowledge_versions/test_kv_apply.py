"""Contract tests of knowledge-versions: apply_memory, the version check, the schema, the budget.
Slice tester; written from the contract, not the code."""

from pathlib import Path

import pytest
from kv_fakes import (
    CHANGES,
    apply_ok,
    change,
    measure_is,
    memory,
    mpath,
    ok_vet,
    rec,
    record,
    seeded,
    snapshot,
    vet_says,
    zero_measure,
)

from thinkhow.knowledge import (
    BUDGET_CHARS,
    CurrentKnowledge,
    MemoryChange,
    MemoryRecord,
    VersionRejected,
    apply_memory,
    current,
)


def test_apply_memory_returns_the_next_rev_and_writes_the_change_record(tmp_path: Path) -> None:
    store = seeded(tmp_path)
    seed_cards = record(store, 1).cards
    first = MemoryChange(
        what="додано m1",
        why="бо так",
        by="synth-run-7",
        upsert=[rec("m1"), rec("m2")],
        remove=[],
        observations=["спостереження 1", "спостереження 2"],
    )
    assert apply_memory(store, first, ok_vet, zero_measure) == 2
    written = record(store, 2)
    assert written.rev == 2
    assert (written.what, written.why, written.by) == ("додано m1", "бо так", "synth-run-7")
    assert written.observations == ["спостереження 1", "спостереження 2"]
    assert written.cards == seed_cards
    assert written.memory == {"m1": mpath("m1", 1), "m2": mpath("m2", 1)}
    assert written.replaced == {"m1": None, "m2": None}
    second = MemoryChange(what="w", why="y", by="b", upsert=[rec("m1", "інакше")], remove=["m2"])
    assert apply_memory(store, second, ok_vet, zero_measure) == 3
    written = record(store, 3)
    assert written.memory == {"m1": mpath("m1", 2)}
    assert written.replaced == {"m1": mpath("m1", 1), "m2": mpath("m2", 1)}
    assert written.observations == []
    data = store.read("system", mpath("m1", 2))
    assert data is not None
    assert MemoryRecord.model_validate_json(data) == rec("m1", "інакше")
    assert memory(store) == {"m1": rec("m1", "інакше")}


def test_apply_memory_numbers_a_version_after_the_largest_existing_one(tmp_path: Path) -> None:
    store = seeded(tmp_path)
    apply_ok(store, [rec("m1")])
    store.put(mpath("m1", 2), rec("m1", "з перерваного прогону").model_dump())  # no record names it
    rev = apply_ok(store, [rec("m1", "нове")])
    assert record(store, rev).memory == {"m1": mpath("m1", 3)}
    assert record(store, rev).replaced == {"m1": mpath("m1", 1)}
    assert memory(store) == {"m1": rec("m1", "нове")}


def test_an_upsert_equal_to_the_current_record_is_neither_versioned_nor_replaced(tmp_path: Path) -> None:
    store = seeded(tmp_path)
    apply_ok(store, [rec("m1"), rec("m2")])
    rev = apply_ok(store, [rec("m1"), rec("m2", "інакше")])
    assert record(store, rev).memory == {"m1": mpath("m1", 1), "m2": mpath("m2", 2)}
    assert record(store, rev).replaced == {"m2": mpath("m2", 1)}
    assert store.read("system", mpath("m1", 2)) is None


def test_a_change_that_changes_nothing_returns_none_and_writes_nothing(tmp_path: Path) -> None:
    store = seeded(tmp_path)
    apply_ok(store, [rec("m1"), rec("m2")])
    root = store.root
    for nothing in (change([rec("m1")]), change([rec("m1"), rec("m2")]), change()):
        before = snapshot(root)
        assert apply_memory(store, nothing, ok_vet, zero_measure) is None
        assert snapshot(root) == before


def test_apply_memory_returns_none_when_another_run_created_the_change_record_first(tmp_path: Path) -> None:
    store = seeded(tmp_path)
    store.forced_prefix = (CHANGES, False)
    assert apply_memory(store, change([rec("m1")]), ok_vet, zero_measure) is None
    assert [p for _, p, _ in store.creates][-1] == f"{CHANGES}000002.json"


def test_apply_memory_writes_only_by_create_if_absent_versions_before_the_record(tmp_path: Path) -> None:
    store = seeded(tmp_path)
    apply_ok(store, [rec("m1")])
    store.creates.clear()
    store.writes.clear()
    assert apply_memory(store, change([rec("m1", "інакше"), rec("m2")]), ok_vet, zero_measure) == 3
    assert store.writes == []
    paths = [p for _, p, _ in store.creates]
    assert paths[-1] == f"{CHANGES}000003.json"
    assert sorted(paths[:-1]) == [mpath("m1", 2), mpath("m2", 1)]


def test_check_1_refuses_a_repeated_upsert_id_and_an_id_both_upserted_and_removed(tmp_path: Path) -> None:
    store = seeded(tmp_path)
    apply_ok(store, [rec("m1")])
    with pytest.raises(VersionRejected):
        apply_memory(store, change([rec("m2"), rec("m2", "друге")]), ok_vet, zero_measure)
    with pytest.raises(VersionRejected):
        apply_memory(store, change([rec("m1"), rec("m1")]), ok_vet, zero_measure)
    with pytest.raises(VersionRejected):
        apply_memory(store, change([rec("m1", "нове")], ["m1"]), ok_vet, zero_measure)
    assert current(store).rev == 2


def test_check_2_refuses_removing_an_id_not_in_the_current_memory(tmp_path: Path) -> None:
    store = seeded(tmp_path)
    r = apply_ok(store, [rec("m1"), rec("m2")])
    apply_ok(store, [], ["m2"])
    with pytest.raises(VersionRejected):
        apply_memory(store, change([], ["m7"]), ok_vet, zero_measure)
    with pytest.raises(VersionRejected):  # removed earlier
        apply_memory(store, change([rec("m3")], ["m2"]), ok_vet, zero_measure)
    assert r == 2
    assert current(store).rev == 3


def test_check_3_refuses_a_record_with_no_cards_or_a_card_not_in_the_current_state(tmp_path: Path) -> None:
    store = seeded(tmp_path)
    with pytest.raises(VersionRejected):
        apply_memory(store, change([rec("m1", cards=[])]), ok_vet, zero_measure)
    with pytest.raises(VersionRejected):
        apply_memory(store, change([rec("m1", cards=["alpha", "gamma"])]), ok_vet, zero_measure)
    assert apply_memory(store, change([rec("m1", cards=["beta", "alpha"])]), ok_vet, zero_measure) == 2


def test_check_4_budget_refuses_over_1_697_152_chars_and_lets_exactly_that_pass(tmp_path: Path) -> None:
    # (1 048 576 - 200 000) x 2 = 1 697 152, by hand
    store = seeded(tmp_path)
    with pytest.raises(VersionRejected) as refused:
        apply_memory(store, change([rec("m1")]), ok_vet, measure_is(1_697_153))
    assert "перевищено бюджет" in refused.value.reason
    assert apply_memory(store, change([rec("m1")]), ok_vet, measure_is(1_697_152)) == 2


def test_measure_gets_the_current_cards_with_the_new_memory(tmp_path: Path) -> None:
    store = seeded(tmp_path)
    apply_ok(store, [rec("m1"), rec("m2"), rec("m3")])
    seen: list[CurrentKnowledge] = []
    assert apply_memory(store, change([rec("m1", "інакше"), rec("m4")], ["m2"]), ok_vet, measure_is(0, seen))
    assert len(seen) == 1
    prospective = seen[0]
    assert prospective.cards == current(store).cards
    assert sorted(prospective.memory, key=lambda r: r.id) == [rec("m1", "інакше"), rec("m3"), rec("m4")]


def test_check_5_refuses_with_the_vet_reason_and_gives_vet_only_the_changing_records(tmp_path: Path) -> None:
    store = seeded(tmp_path)
    apply_ok(store, [rec("m1"), rec("m2")])
    calls: list[list[MemoryRecord]] = []
    with pytest.raises(VersionRejected) as refused:
        apply_memory(
            store,
            change([rec("m1"), rec("m2", "Олена зі Львова"), rec("m3")]),
            vet_says("названо людину", calls),
            zero_measure,
        )
    assert "подробиці людей" in refused.value.reason
    assert "названо людину" in refused.value.reason
    assert len(calls) == 1
    assert sorted(calls[0], key=lambda r: r.id) == [rec("m2", "Олена зі Львова"), rec("m3")]
    assert current(store).rev == 2


def test_vet_is_not_called_when_no_record_changes(tmp_path: Path) -> None:
    store = seeded(tmp_path)
    apply_ok(store, [rec("m1"), rec("m2")])
    calls: list[list[MemoryRecord]] = []
    assert apply_memory(store, change([rec("m1")], ["m2"]), vet_says("ні", calls), zero_measure) == 3
    assert calls == []
    assert memory(store) == {"m1": rec("m1")}


def test_a_failing_check_stops_the_checks_after_it(tmp_path: Path) -> None:
    store = seeded(tmp_path)
    apply_ok(store, [rec("m1")])
    for bad in (
        change([rec("m2"), rec("m2")]),  # 1
        change([rec("m2")], ["m9"]),  # 2
        change([rec("m2", cards=["gamma"])]),  # 3
    ):
        seen: list[CurrentKnowledge] = []
        calls: list[list[MemoryRecord]] = []
        with pytest.raises(VersionRejected):
            apply_memory(store, bad, vet_says("причина", calls), measure_is(BUDGET_CHARS + 1, seen))
        assert seen == [] and calls == [], bad
    calls = []
    with pytest.raises(VersionRejected) as refused:
        apply_memory(store, change([rec("m2")]), vet_says("причина", calls), measure_is(BUDGET_CHARS + 1))
    assert "перевищено бюджет" in refused.value.reason
    assert calls == []


def test_old_records_without_the_new_fields_are_read_and_built_on(tmp_path: Path) -> None:
    store = seeded(tmp_path)
    cards = record(store, 1).cards
    old_memory = {
        "id": "m-old",
        "title": "старий",
        "cards": ["alpha"],
        "noticed": "н",
        "do": "д",
        "basis": "п",
    }
    store.put(mpath("m-old", 1), old_memory)
    store.put(
        f"{CHANGES}000002.json",
        {"rev": 2, "what": "w", "why": "y", "cards": cards, "memory": {"m-old": mpath("m-old", 1)}},
    )
    knowledge = current(store)
    assert (knowledge.rev, knowledge.n) == (2, 0)
    assert knowledge.memory[0].audience == "facilitator"
    old = record(store, 2)
    assert (old.observations, old.by, old.replaced) == ([], "", {})
    assert apply_ok(store, [rec("m1", audience="router")], ["m-old"]) == 3
    assert memory(store) == {"m1": rec("m1", audience="router")}
    assert record(store, 3).replaced == {"m1": None, "m-old": mpath("m-old", 1)}
