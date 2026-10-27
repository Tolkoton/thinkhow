"""Contract tests of knowledge-versions: the change feed `changes()` (slice tester; from the contract)."""

from pathlib import Path

from kv_fakes import NOW, ROLLBACKS, apply_ok, mpath, ok_vet, rec, seeded, zero_measure

from thinkhow.knowledge import ChangeView, MemoryChange, apply_memory, changes, rollback


def test_changes_gives_the_memory_revisions_newest_first_with_their_fields(tmp_path: Path) -> None:
    store = seeded(tmp_path)
    first = MemoryChange(
        what="перша",
        why="чому 1",
        by="synth-1",
        upsert=[rec("m1"), rec("m2")],
        remove=[],
        observations=["о1"],
    )
    assert apply_memory(store, first, ok_vet, zero_measure) == 2
    second = MemoryChange(
        what="друга", why="чому 2", by="synth-2", upsert=[rec("m1", "інакше"), rec("m2")], remove=[]
    )
    assert apply_memory(store, second, ok_vet, zero_measure) == 3
    third = MemoryChange(what="третя", why="чому 3", by="synth-3", upsert=[rec("m3")], remove=["m2"])
    assert apply_memory(store, third, ok_vet, zero_measure) == 4
    feed = changes(store)
    revs = [view.rev for view in feed]
    assert revs == sorted(revs, reverse=True)
    views = {view.rev: view for view in feed}
    assert set(views) >= {2, 3, 4}
    assert all(isinstance(view, ChangeView) for view in feed)
    v2, v3, v4 = views[2], views[3], views[4]
    assert (v2.what, v2.why, v2.by, v2.observations) == ("перша", "чому 1", "synth-1", ["о1"])
    assert sorted(v2.upserted, key=lambda r: r.id) == [rec("m1"), rec("m2")]
    assert v2.removed == []
    assert v3.upserted == [rec("m1", "інакше")]  # m2 did not change
    assert v3.removed == []
    assert (v4.what, v4.by, v4.observations) == ("третя", "synth-3", [])
    assert v4.upserted == [rec("m3")]
    assert v4.removed == ["m2"]
    assert all(views[r].rolled_back is None for r in (2, 3, 4))


def test_changes_names_the_rollback_of_a_revision_and_what_it_changed(tmp_path: Path) -> None:
    store = seeded(tmp_path)
    apply_ok(store, [rec("m1", "v1")])
    r3 = apply_ok(store, [rec("m1", "v2"), rec("m2")])
    r4 = apply_ok(store, [rec("m1", "v3")])
    assert rollback(store, r3, "owner", NOW) == 1  # m1 kept (changed by r4), m2 gone
    assert rollback(store, r4, "owner", NOW) == 2  # m1 back to v2
    views = {view.rev: view for view in changes(store)}
    assert views[2].rolled_back is None
    assert (views[r3].rolled_back, views[r3].rollback_changed) == (1, ["m2"])
    assert (views[r4].rolled_back, views[r4].rollback_changed) == (2, ["m1"])


def test_changes_gives_the_smallest_n_of_two_concurrent_rollbacks_of_one_revision(tmp_path: Path) -> None:
    store = seeded(tmp_path)
    r = apply_ok(store, [rec("m1")])
    assert rollback(store, r, "owner", NOW) == 1
    store.put(
        f"{ROLLBACKS}000002.json",
        {
            "n": 2,
            "rev": r,
            "reverts": {"m1": mpath("m1", 1)},
            "restore": {"m1": None},
            "changed": [],
            "at": NOW.isoformat(),
            "by": "owner",
        },
    )
    views = {view.rev: view for view in changes(store)}
    assert views[r].rolled_back == 1
