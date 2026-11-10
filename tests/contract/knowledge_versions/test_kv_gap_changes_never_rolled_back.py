"""Test gap from the overseer (task 719): a revision never rolled back shows no rollback in `changes()`."""

from pathlib import Path

from kv_fakes import NOW, apply_ok, rec, seeded

from thinkhow.knowledge import changes, rollback


def test_changes_rollback_changed_is_empty_for_a_revision_never_rolled_back(tmp_path: Path) -> None:
    store = seeded(tmp_path)
    before = apply_ok(store, [rec("m1", "v1"), rec("m2", "v1")])
    rolled = apply_ok(store, [rec("m1", "v2"), rec("m2", "v2")])
    assert rollback(store, rolled, "owner", NOW) == 1  # m1 and m2 back to v1
    after = apply_ok(store, [rec("m1", "v3")])
    views = {view.rev: view for view in changes(store)}
    assert views[rolled].rolled_back == 1
    assert views[rolled].rollback_changed  # the rollback did act, so there is something to leak
    for rev in (before, after):  # both changed ids the rollback reverted
        assert (views[rev].rolled_back, views[rev].rollback_changed) == (None, [])
