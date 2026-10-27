"""Contract tests of knowledge-versions: rollback, the rollback rule in current(), publish after a rollback.
Slice tester; written from the contract, not the code."""

from datetime import datetime
from pathlib import Path

import pytest
from kv_fakes import (
    CARDS,
    CHANGES,
    NOW,
    ROLLBACKS,
    RecordingStorage,
    apply_ok,
    memory,
    mpath,
    rec,
    record,
    seeded,
    snapshot,
    write_cards,
)

from thinkhow.knowledge import (
    AlreadyRolledBack,
    KnowledgeConflict,
    KnowledgeCorrupt,
    NotRollbackable,
    Rollback,
    UnknownRevision,
    current,
    publish,
    rollback,
)


def rollback_file(store: RecordingStorage, n: int) -> Rollback:
    data = store.read("system", f"{ROLLBACKS}{n:06d}.json")
    assert data is not None, n
    return Rollback.model_validate_json(data)


def test_rollback_writes_its_file_and_returns_n(tmp_path: Path) -> None:
    store = seeded(tmp_path)
    apply_ok(store, [rec("m1"), rec("m2")])
    r = apply_ok(store, [rec("m1", "інакше"), rec("m3")], ["m2"])
    assert rollback(store, r, "owner@x", NOW) == 1
    written = rollback_file(store, 1)
    assert (written.n, written.rev, written.by, written.at) == (1, r, "owner@x", NOW)
    assert written.reverts == {"m1": mpath("m1", 2), "m2": None, "m3": mpath("m3", 1)}
    assert written.restore == {"m1": mpath("m1", 1), "m2": mpath("m2", 1), "m3": None}
    assert sorted(written.changed) == ["m1", "m2", "m3"]
    assert memory(store) == {"m1": rec("m1"), "m2": rec("m2")}


def test_rollback_writes_only_by_create_if_absent_and_never_a_card_file(tmp_path: Path) -> None:
    store = seeded(tmp_path)
    r = apply_ok(store, [rec("m1")])
    cards = snapshot(store.root, CARDS)
    changes = snapshot(store.root, CHANGES)
    store.creates.clear()
    store.writes.clear()
    rollback(store, r, "owner", NOW)
    assert store.writes == []
    assert [p for _, p, _ in store.creates] == [f"{ROLLBACKS}000001.json"]
    assert snapshot(store.root, CARDS) == cards
    assert snapshot(store.root, CHANGES) == changes
    assert record(store, r).cards == record(store, 1).cards


def test_rollback_of_a_missing_rev_raises_unknown_revision(tmp_path: Path) -> None:
    store = seeded(tmp_path)
    apply_ok(store, [rec("m1")])
    for rev in (3, 99):
        with pytest.raises(UnknownRevision):
            rollback(store, rev, "owner", NOW)


def test_rollback_of_a_seed_or_publish_revision_raises_not_rollbackable(tmp_path: Path) -> None:
    store = seeded(tmp_path)
    with pytest.raises(NotRollbackable):
        rollback(store, 1, "owner", NOW)
    apply_ok(store, [rec("m1")])
    write_cards(tmp_path / "cards", {"alpha": "Альфа нова", "beta": "Бета"})
    published = publish(store, tmp_path / "cards")
    assert published == 3
    with pytest.raises(NotRollbackable):
        rollback(store, published, "owner", NOW)


def test_a_second_rollback_of_the_same_rev_raises_already_rolled_back(tmp_path: Path) -> None:
    store = seeded(tmp_path)
    r = apply_ok(store, [rec("m1")])
    apply_ok(store, [rec("m2")])
    rollback(store, r, "owner", NOW)
    with pytest.raises(AlreadyRolledBack):
        rollback(store, r, "owner", NOW)
    assert current(store).n == 1


def test_rollback_refuses_a_now_without_a_time_zone(tmp_path: Path) -> None:
    store = seeded(tmp_path)
    r = apply_ok(store, [rec("m1")])
    with pytest.raises(ValueError):
        rollback(store, r, "owner", datetime(2026, 10, 27, 12, 0))


def test_rollback_takes_the_next_number_when_another_run_took_one(tmp_path: Path) -> None:
    store = seeded(tmp_path)
    other = apply_ok(store, [rec("m2")])
    r = apply_ok(store, [rec("m3")])
    taken: list[str] = []

    def rival(s: RecordingStorage, path: str) -> None:
        if not taken:
            taken.append(path)
            s.put(
                path,
                {
                    "n": 1,
                    "rev": other,
                    "reverts": {"m2": mpath("m2", 1)},
                    "restore": {"m2": None},
                    "changed": ["m2"],
                    "at": NOW.isoformat(),
                    "by": "rival",
                },
            )

    store.rival = rival
    assert rollback(store, r, "owner", NOW) == 2
    assert taken == [f"{ROLLBACKS}000001.json"]
    assert rollback_file(store, 2).rev == r
    assert rollback_file(store, 1).by == "rival"
    assert memory(store) == {}


def test_rollback_raises_knowledge_conflict_when_other_runs_keep_taking_the_number(tmp_path: Path) -> None:
    store = seeded(tmp_path)
    other = apply_ok(store, [rec("m2")])
    r = apply_ok(store, [rec("m3")])

    def rival(s: RecordingStorage, path: str) -> None:
        n = int(path.removeprefix(ROLLBACKS).removesuffix(".json"))
        s.put(
            path,
            {
                "n": n,
                "rev": other,
                "reverts": {"m2": mpath("m2", 1)},
                "restore": {"m2": None},
                "changed": ["m2"],
                "at": NOW.isoformat(),
                "by": "rival",
            },
        )

    store.rival = rival
    with pytest.raises(KnowledgeConflict):
        rollback(store, r, "owner", NOW)
    assert all(rollback_file(store, n).by == "rival" for n in range(1, current(store).n + 1))


def test_seam1_rollback_after_a_later_change_of_the_same_id_changes_nothing(tmp_path: Path) -> None:
    store = seeded(tmp_path)
    apply_ok(store, [rec("m1", "v1")])
    r2 = apply_ok(store, [rec("m1", "v2")])
    apply_ok(store, [rec("m1", "v3")])
    assert rollback(store, r2, "owner", NOW) == 1
    assert memory(store) == {"m1": rec("m1", "v3")}
    assert rollback_file(store, 1).changed == []
    assert current(store).n == 1


def test_seam2_a_revision_after_a_rollback_is_built_from_the_current_state(tmp_path: Path) -> None:
    store = seeded(tmp_path)
    r = apply_ok(store, [rec("m1")])
    rollback(store, r, "owner", NOW)
    r3 = apply_ok(store, [rec("m2")])
    assert memory(store) == {"m2": rec("m2")}
    assert record(store, r3).memory == {"m2": mpath("m2", 1)}
    assert record(store, r3).replaced == {"m2": None}


def test_seam2_publish_after_a_rollback_takes_the_current_memory_and_replaces_nothing(tmp_path: Path) -> None:
    store = seeded(tmp_path)
    apply_ok(store, [rec("m1", "v1")])
    r = apply_ok(store, [rec("m1", "v2"), rec("m2")])
    rollback(store, r, "owner", NOW)
    write_cards(tmp_path / "cards", {"alpha": "Альфа нова", "beta": "Бета"})
    published = publish(store, tmp_path / "cards")
    assert published == 4
    assert record(store, published).memory == {"m1": mpath("m1", 1)}
    assert record(store, published).replaced == {}
    assert memory(store) == {"m1": rec("m1", "v1")}


def test_seam6a_a_removal_rolled_back_then_removed_again_stays_removed(tmp_path: Path) -> None:
    store = seeded(tmp_path)
    apply_ok(store, [rec("m1")])
    r = apply_ok(store, [], ["m1"])
    rollback(store, r, "owner", NOW)
    assert memory(store) == {"m1": rec("m1")}
    apply_ok(store, [], ["m1"])
    assert memory(store) == {}
    apply_ok(store, [rec("m2")])
    assert memory(store) == {"m2": rec("m2")}


def test_seam6b_rollback_of_a_removal_after_re_add_and_re_removal_brings_nothing_back(tmp_path: Path) -> None:
    store = seeded(tmp_path)
    apply_ok(store, [rec("m1", "v1")])
    r = apply_ok(store, [], ["m1"])
    apply_ok(store, [rec("m1", "v2")])
    apply_ok(store, [], ["m1"])
    rollback(store, r, "owner", NOW)
    assert memory(store) == {}
    assert "m1" not in rollback_file(store, 1).changed


def test_seam6c_the_q2_chain_in_reverse_order_ends_at_the_first_version(tmp_path: Path) -> None:
    store = seeded(tmp_path)
    apply_ok(store, [rec("m1", "p1")])
    r2 = apply_ok(store, [rec("m1", "p2")])
    r3 = apply_ok(store, [rec("m1", "p3")])
    rollback(store, r3, "owner", NOW)
    assert memory(store) == {"m1": rec("m1", "p2")}
    rollback(store, r2, "owner", NOW)
    assert memory(store) == {"m1": rec("m1", "p1")}
    assert rollback_file(store, 2).changed == ["m1"]


def test_seam6c_the_q2_chain_in_forward_order_ends_at_the_middle_version(tmp_path: Path) -> None:
    store = seeded(tmp_path)
    apply_ok(store, [rec("m1", "p1")])
    r2 = apply_ok(store, [rec("m1", "p2")])
    r3 = apply_ok(store, [rec("m1", "p3")])
    rollback(store, r2, "owner", NOW)
    assert memory(store) == {"m1": rec("m1", "p3")}
    assert rollback_file(store, 1).changed == []
    rollback(store, r3, "owner", NOW)
    assert memory(store) == {"m1": rec("m1", "p2")}
    assert rollback_file(store, 2).changed == ["m1"]


def test_seam6d_a_rollback_holds_over_a_concurrent_revision_that_did_not_see_it(tmp_path: Path) -> None:
    store = seeded(tmp_path)
    r = apply_ok(store, [rec("m1")])
    rollback(store, r, "owner", NOW)
    # revision 3 by a run that read revision 2 and never saw the rollback: the raw m1 = the value of reverts
    store.put(mpath("m2", 1), rec("m2").model_dump())
    store.put(
        f"{CHANGES}000003.json",
        {
            "rev": 3,
            "what": "w",
            "why": "y",
            "by": "synth",
            "observations": [],
            "cards": record(store, 2).cards,
            "memory": {"m1": mpath("m1", 1), "m2": mpath("m2", 1)},
            "replaced": {"m2": None},
        },
    )
    assert rollback_file(store, 1).reverts == {"m1": mpath("m1", 1)}
    assert memory(store) == {"m2": rec("m2")}


def test_current_refuses_a_rollback_naming_a_rev_after_the_last_record(tmp_path: Path) -> None:
    store = seeded(tmp_path)
    apply_ok(store, [rec("m1")])
    store.put(
        f"{ROLLBACKS}000001.json",
        {"n": 1, "rev": 3, "reverts": {}, "restore": {}, "changed": [], "at": NOW.isoformat(), "by": "owner"},
    )
    with pytest.raises(KnowledgeCorrupt):
        current(store)
