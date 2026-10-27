"""The invariants I1–I3 of starting-notes (slice tester): inputs chosen by hand from each «Domain»."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml
from sn_fakes import (
    Job,
    VetLlm,
    as_record,
    card_dict,
    change_files,
    facilitator,
    hand_change,
    memory,
    newest_record,
    note_dict,
    router,
)

from thinkhow.knowledge import changes, rollback

LATER = datetime(2026, 10, 28, 9, 0, 0, tzinfo=UTC)


@pytest.fixture
def jb(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Job:
    j = Job(tmp_path, monkeypatch)
    j.seed()
    return j


def _paths(jb: Job) -> dict[str, str]:
    return dict(newest_record(jb.storage).memory)


def test_I1_notes_leaves_every_record_that_was_there_the_same_version(
    jb: Job, monkeypatch: pytest.MonkeyPatch
) -> None:
    # memory of another writer before any notes
    syn_a = as_record(note_dict("syn-a", ["alpha"], "facilitator"))
    syn_b = as_record(note_dict("syn-b", ["beta", "gamma"], "router"))
    hand_change(jb.storage, upsert=[syn_a, syn_b])
    jb.put("alpha.yaml", [router("alpha", "beta"), facilitator("alpha")])
    before, paths = memory(jb.storage), _paths(jb)
    # a refused run first: nothing changes
    real_make_llm = __import__("thinkhow.learning.job", fromlist=["make_llm"]).make_llm
    jb.use_llm(VetLlm(ok=False, reason="подробиці"))
    assert jb("notes") == 1
    assert memory(jb.storage) == before and _paths(jb) == paths
    monkeypatch.setattr("thinkhow.learning.job.make_llm", real_make_llm)
    # the lawful run after it
    assert jb("notes") == 0
    after, after_paths = memory(jb.storage), _paths(jb)
    for mid in ("syn-a", "syn-b"):
        assert after[mid] == before[mid] and after_paths[mid] == paths[mid], mid
    assert "alpha-router" in after and "alpha-facilitator" in after
    # the synthesizer rewrites a published note; the repository's copy of it changes too; a new file appears
    learned = as_record(router("alpha", "beta", noticed="вивчено синтезатором"))
    hand_change(jb.storage, upsert=[learned])
    jb.put(
        "alpha.yaml", [router("alpha", noticed="правка в репозиторії"), facilitator("alpha", noticed="теж")]
    )
    jb.put("beta.yaml", [router("beta"), facilitator("beta")])
    before, paths = memory(jb.storage), _paths(jb)
    assert jb("notes") == 0
    after, after_paths = memory(jb.storage), _paths(jb)
    for mid in ("syn-a", "syn-b", "alpha-router", "alpha-facilitator"):
        assert after[mid] == before[mid] and after_paths[mid] == paths[mid], mid
    assert after["alpha-router"] == learned
    assert sorted(set(after) - set(before)) == ["beta-facilitator", "beta-router"]
    # a folder that brings nothing new: everything stays
    before, paths = memory(jb.storage), _paths(jb)
    assert jb("notes") == 0
    assert memory(jb.storage) == before and _paths(jb) == paths


def test_I2_a_second_notes_run_on_the_same_folder_creates_no_revision(jb: Job) -> None:
    # right after seed, with a router note naming a neighbour card
    jb.put("alpha.yaml", [router("alpha", "beta", "gamma"), facilitator("alpha")])
    assert jb("notes") == 0
    files = change_files(jb.storage)
    assert len(files) == 2
    assert jb("notes") == 0
    assert change_files(jb.storage) == files
    # after the synthesizer changed one note and removed another
    hand_change(jb.storage, upsert=[as_record(facilitator("alpha", noticed="інакше"))])
    hand_change(jb.storage, remove=["alpha-router"])
    assert jb("notes") == 0
    files = change_files(jb.storage)
    assert jb("notes") == 0
    assert change_files(jb.storage) == files
    # a folder grown by one file: the first run publishes it, the second nothing
    jb.put("gamma.yaml", [router("gamma"), facilitator("gamma")])
    assert jb("notes") == 0
    files = change_files(jb.storage)
    assert jb("notes") == 0
    assert change_files(jb.storage) == files
    # after a rollback of that notes revision
    rollback(jb.storage, int(files[-1].rsplit("/", 1)[-1].split(".")[0]), "owner", LATER)
    assert jb("notes") == 0
    files = change_files(jb.storage)
    assert jb("notes") == 0
    assert change_files(jb.storage) == files


def test_I3_notes_never_upserts_an_id_a_notes_change_once_upserted(jb: Job) -> None:
    published = ["alpha-facilitator", "alpha-router", "beta-router"]
    jb.put("alpha.yaml", [router("alpha", "beta"), facilitator("alpha")])
    jb.put("beta.yaml", [router("beta")])
    assert jb("notes") == 0
    notes_rev = changes(jb.storage)[0].rev
    hand_change(jb.storage, upsert=[as_record(router("alpha", "beta", noticed="синтезатор"))])
    removal = hand_change(jb.storage, remove=["beta-router"])
    rollback(jb.storage, notes_rev, "owner", LATER)
    # a publish of changed cards (the Job's `cards`) in the history too
    text = yaml.safe_dump(card_dict("alpha", "Альфа нова"), allow_unicode=True, sort_keys=False)
    (jb.cards / "alpha.yaml").write_text(text, encoding="utf-8")
    assert jb("cards") == 0
    hand_change(jb.storage, upsert=[as_record(note_dict("syn-x", ["gamma"], "facilitator"))], by="owner-test")
    assert removal < changes(jb.storage)[0].rev
    # the folder: every published id (one of them with new text) and one id never published
    jb.put(
        "alpha.yaml", [router("alpha", noticed="нова правка"), facilitator("alpha", noticed="нова правка")]
    )
    jb.put("beta.yaml", [router("beta", noticed="повернути?")])
    jb.put("gamma.yaml", [facilitator("gamma")])
    before = changes(jb.storage)[0].rev
    assert jb("notes") == 0
    newer = [view for view in changes(jb.storage) if view.rev > before]
    assert len(newer) == 1
    assert newer[0].by == "notes"
    assert [r.id for r in newer[0].upserted] == ["gamma-facilitator"]
    for mid in published:
        assert all(mid not in [r.id for r in view.upserted] for view in newer), mid
    # and once more, after a rollback of that revision too: nothing at all
    rollback(jb.storage, newer[0].rev, "owner", LATER)
    files = change_files(jb.storage)
    assert jb("notes") == 0
    assert change_files(jb.storage) == files
