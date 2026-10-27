"""Contract tests of knowledge-versions: the invariants I1-I7 (slice tester; from the contract)."""

from collections.abc import Sequence
from pathlib import Path

import pytest
from kv_fakes import (
    CARDS,
    NOW,
    apply_ok,
    change,
    measure_is,
    memory,
    mpath,
    rec,
    record,
    seeded,
    snapshot,
    vet_says,
    write_cards,
)

from thinkhow.knowledge import (
    BUDGET_CHARS,
    MemoryRecord,
    VersionRejected,
    apply_memory,
    current,
    publish,
    rollback,
)
from thinkhow.platform.llm import KnowledgeRev


def test_I1_a_memory_change_keeps_the_cards_dict_and_every_card_file(tmp_path: Path) -> None:
    store = seeded(tmp_path)
    root = store.root
    steps: list[tuple[Sequence[MemoryRecord], Sequence[str]]] = [
        ([rec("m1"), rec("m2", cards=["alpha", "beta"])], []),  # new ids
        ([rec("m1", "інакше")], ["m2"]),  # a changed id and a removal
        ([], ["m1"]),  # a removal only
    ]
    for upsert, remove in steps:
        cards_before = current(store).cards
        record_cards = record(store, current(store).rev).cards
        files = snapshot(root, CARDS)
        rev = apply_ok(store, upsert, remove)
        assert record(store, rev).cards == record_cards
        assert current(store).cards == cards_before
        assert snapshot(root, CARDS) == files
    # after a publish moved a card to v2, and after a rollback
    write_cards(tmp_path / "cards", {"alpha": "Альфа нова", "beta": "Бета"})
    published = publish(store, tmp_path / "cards")
    assert isinstance(published, int)
    rolled = apply_ok(store, [rec("m3")])
    rollback(store, rolled, "owner", NOW)
    for upsert in ([rec("m4", cards=["beta"])], [rec("m3", "знову")]):
        record_cards = record(store, current(store).rev).cards
        files = snapshot(root, CARDS)
        rev = apply_ok(store, upsert)
        assert record(store, rev).cards == record_cards == record(store, published).cards
        assert snapshot(root, CARDS) == files


def test_I2_rolling_back_the_last_change_gives_the_memory_from_before_it(tmp_path: Path) -> None:
    store = seeded(tmp_path)
    apply_ok(store, [rec("m1"), rec("m2"), rec("m3")])
    cases: list[tuple[Sequence[MemoryRecord], Sequence[str]]] = [
        ([rec("m4")], []),  # a new id
        ([rec("m1", "змінено")], []),  # an existing id
        ([], ["m2"]),  # a removal
        ([rec("m5"), rec("m3", "теж змінено")], ["m1", "m2"]),  # all three at once
        ([rec("m1", "помічено")], ["m3"]),  # an upsert equal to the current one, with a removal
    ]
    for upsert, remove in cases:
        before = current(store).memory
        rev = apply_ok(store, upsert, remove)
        assert current(store).memory != before
        rollback(store, rev, "owner", NOW)
        assert current(store).memory == before, (upsert, remove)
    # from an empty memory
    empty = seeded(tmp_path / "empty")
    rev = apply_ok(empty, [rec("m1")])
    rollback(empty, rev, "owner", NOW)
    assert current(empty).memory == []


def test_I3_a_rollback_keeps_what_later_revisions_changed(tmp_path: Path) -> None:
    # a later revision changed the same id
    store = seeded(tmp_path / "same")
    apply_ok(store, [rec("m1", "v1")])
    r = apply_ok(store, [rec("m1", "v2"), rec("m2", "v1")])
    apply_ok(store, [rec("m1", "v3")])
    rollback(store, r, "owner", NOW)
    assert memory(store) == {"m1": rec("m1", "v3")}
    # a later revision removed what R added; another later revision changed another id
    store = seeded(tmp_path / "removed")
    apply_ok(store, [rec("m9")])
    r = apply_ok(store, [rec("m1"), rec("m2")])
    apply_ok(store, [], ["m1"])
    apply_ok(store, [rec("m9", "інакше")])
    rollback(store, r, "owner", NOW)
    assert memory(store) == {"m9": rec("m9", "інакше")}
    # a later revision added back what R removed
    store = seeded(tmp_path / "readded")
    apply_ok(store, [rec("m1", "v1")])
    r = apply_ok(store, [], ["m1"])
    apply_ok(store, [rec("m1", "v2")])
    rollback(store, r, "owner", NOW)
    assert memory(store) == {"m1": rec("m1", "v2")}


def test_I4_every_refused_change_leaves_the_system_files_as_they_were(tmp_path: Path) -> None:
    store = seeded(tmp_path)
    apply_ok(store, [rec("m1"), rec("m2")])
    root = store.root

    cases = [
        (change([rec("m3"), rec("m3", "друге")]), None, 0),  # 1: the same id twice in upsert
        (change([rec("m1", "нове")], ["m1"]), None, 0),  # 1: an id both in upsert and remove
        (change([], ["m7"]), None, 0),  # 2: removing an id not in the memory
        (change([rec("m3", cards=[])]), None, 0),  # 3: empty cards
        (change([rec("m3", cards=["alpha", "gamma"])]), None, 0),  # 3: a card not in the current state
        (change([rec("m3")]), None, BUDGET_CHARS + 1),  # 4: over the budget
        (change([rec("m3")]), "ім'я людини", 0),  # 5: the vet's reason
    ]
    for bad, reason, size in cases:
        before = snapshot(root)
        with pytest.raises(VersionRejected):
            apply_memory(store, bad, vet_says(reason), measure_is(size))
        assert snapshot(root) == before, bad


def test_I5_a_rollback_holds_through_later_changes_and_publish(tmp_path: Path) -> None:
    store = seeded(tmp_path)
    apply_ok(store, [rec("m1", "v1")])
    added = apply_ok(store, [rec("m2")])
    replaced = apply_ok(store, [rec("m1", "v2")])
    gone = apply_ok(store, [rec("m3")])
    killed = apply_ok(store, [], ["m3"])
    rollback(store, killed, "owner", NOW)  # m3 back
    rollback(store, gone, "owner", NOW)  # rev of m3 later removed (the removal is rolled back) -> m3 gone
    rollback(store, replaced, "owner", NOW)  # m1 back to v1
    rollback(store, added, "owner", NOW)  # m2 gone
    expected = {"m1": rec("m1", "v1")}
    assert memory(store) == expected
    apply_ok(store, [rec("m4")])
    expected["m4"] = rec("m4")
    assert memory(store) == expected
    write_cards(tmp_path / "cards", {"alpha": "Альфа нова", "beta": "Бета"})
    assert isinstance(publish(store, tmp_path / "cards"), int)
    assert memory(store) == expected
    apply_ok(store, [rec("m5")], ["m4"])
    assert memory(store) == {"m1": rec("m1", "v1"), "m5": rec("m5")}
    # unless the change itself upserts them
    apply_ok(store, [rec("m2", "знову"), rec("m1", "v2")])
    assert memory(store) == {"m1": rec("m1", "v2"), "m2": rec("m2", "знову"), "m5": rec("m5")}


def test_I6_rev_pair_is_the_largest_rev_and_the_largest_rollback_n(tmp_path: Path) -> None:
    store = seeded(tmp_path)
    assert current(store).rev_pair() == KnowledgeRev(rev=1, n=0)
    a = apply_ok(store, [rec("m1")])
    b = apply_ok(store, [rec("m2")])
    c = apply_ok(store, [rec("m1", "v2")])
    assert current(store).rev_pair() == KnowledgeRev(rev=4, n=0)
    assert rollback(store, b, "owner", NOW) == 1
    assert current(store).rev_pair() == KnowledgeRev(rev=4, n=1)
    assert rollback(store, a, "owner", NOW) == 2  # acts on nothing now (m1 changed by c): still counts
    assert current(store).rev_pair() == KnowledgeRev(rev=4, n=2)
    apply_ok(store, [rec("m3")])
    assert current(store).rev_pair() == KnowledgeRev(rev=5, n=2)
    assert rollback(store, c, "owner", NOW) == 3
    assert current(store).rev_pair() == KnowledgeRev(rev=5, n=3)
    # rollbacks written at the same time by two runs (by hand): n = 4 and 5
    for n in (4, 5):
        store.put(
            f"knowledge/rollbacks/{n:06d}.json",
            {
                "n": n,
                "rev": 5,
                "reverts": {"m3": mpath("m3", 1)},
                "restore": {"m3": None},
                "changed": ["m3"],
                "at": NOW.isoformat(),
                "by": "owner",
            },
        )
    assert current(store).rev_pair() == KnowledgeRev(rev=5, n=5)


def test_I7_a_change_written_after_a_rollback_stays(tmp_path: Path) -> None:
    # a removal rolled back, then the same id removed again
    store = seeded(tmp_path / "remove")
    apply_ok(store, [rec("m1")])
    r = apply_ok(store, [], ["m1"])
    rollback(store, r, "owner", NOW)
    assert memory(store) == {"m1": rec("m1")}
    apply_ok(store, [], ["m1"])
    assert memory(store) == {}
    apply_ok(store, [rec("m2")])
    apply_ok(store, [rec("m3")])
    assert memory(store) == {"m2": rec("m2"), "m3": rec("m3")}
    # an upsert of a new id rolled back, then the id upserted again
    store = seeded(tmp_path / "add")
    r = apply_ok(store, [rec("m1", "v1")])
    rollback(store, r, "owner", NOW)
    assert memory(store) == {}
    apply_ok(store, [rec("m1", "v2")])
    assert memory(store) == {"m1": rec("m1", "v2")}
    apply_ok(store, [rec("m2")])
    assert memory(store) == {"m1": rec("m1", "v2"), "m2": rec("m2")}
    # a replacement rolled back, then the id changed again, then removed
    store = seeded(tmp_path / "replace")
    apply_ok(store, [rec("m1", "v1")])
    r = apply_ok(store, [rec("m1", "v2")])
    rollback(store, r, "owner", NOW)
    assert memory(store) == {"m1": rec("m1", "v1")}
    apply_ok(store, [rec("m1", "v3")])
    assert memory(store) == {"m1": rec("m1", "v3")}
    apply_ok(store, [], ["m1"])
    apply_ok(store, [rec("m2")])
    assert memory(store) == {"m2": rec("m2")}
    assert record(store, current(store).rev).memory == {"m2": mpath("m2", 1)}
