"""Task 746: the feed shows what a rollback changed when it was made — its stored `changed` — as history."""

import json
from pathlib import Path

from kv_fakes import NOW, apply_ok, rec, seeded

from thinkhow.knowledge import changes, rollback


def test_a_later_revision_of_the_reverted_id_does_not_empty_the_rollbacks_changed_in_the_feed(
    tmp_path: Path,
) -> None:
    store = seeded(tmp_path)
    apply_ok(store, [rec("m1", "v1")])
    rolled = apply_ok(store, [rec("m1", "v2")])
    assert rollback(store, rolled, "owner", NOW) == 1  # m1 back to v1
    assert {v.rev: v.rollback_changed for v in changes(store)}[rolled] == ["m1"]

    apply_ok(store, [rec("m1", "v3")])

    stored = json.loads(store.read("system", "knowledge/rollbacks/000001.json") or b"")
    view = next(v for v in changes(store) if v.rev == rolled)
    assert (view.rolled_back, view.rollback_changed, stored["changed"]) == (1, ["m1"], ["m1"])
