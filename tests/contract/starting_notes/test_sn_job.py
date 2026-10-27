"""Contract tests of the Job command `notes` (slice tester; from the contract, not the code).

Local mode on a temporary folder: `seed` of alpha, beta, gamma, then `notes` from `notes/` beside `cards/`.
"""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import BaseModel, ValidationError
from sn_fakes import (
    CARDS_PREFIX,
    WHAT,
    WHY,
    Job,
    VetLlm,
    as_record,
    change_files,
    events,
    facilitator,
    hand_change,
    memory,
    newest_record,
    router,
    snapshot,
)

from thinkhow.knowledge import changes, current, rollback
from thinkhow.platform.llm import LlmUnavailable

LATER = datetime(2026, 10, 28, 9, 0, 0, tzinfo=UTC)


@pytest.fixture
def jb(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Job:
    j = Job(tmp_path, monkeypatch)
    j.seed()
    return j


def three(jb: Job) -> list[dict[str, object]]:
    alpha = [router("alpha", "beta"), facilitator("alpha")]
    beta = [router("beta")]
    jb.put("alpha.yaml", alpha)
    jb.put("beta.yaml", beta)
    return alpha + beta


def test_notes_publishes_one_revision_by_notes_with_the_folders_records(
    jb: Job, capsys: pytest.CaptureFixture[str]
) -> None:
    items = three(jb)
    capsys.readouterr()
    assert jb("notes") == 0
    now = current(jb.storage)
    assert now.rev == 2
    assert memory(jb.storage) == {r.id: r for r in (as_record(i) for i in items)}
    record = newest_record(jb.storage)
    assert record.rev == 2
    assert record.by == "notes"
    assert record.what == f"{WHAT}3"
    assert record.why == WHY
    assert sorted(record.memory) == ["alpha-facilitator", "alpha-router", "beta-router"]
    view = changes(jb.storage)[0]
    assert view.rev == 2 and view.by == "notes" and view.removed == []
    published = events(capsys.readouterr().out, "notes_published")
    assert len(published) == 1
    line = published[0]
    assert line["rev"] == 2
    assert 3 in [v for k, v in line.items() if k not in ("rev", "event", "severity", "request_id")]


def test_notes_a_second_run_on_the_same_folder_creates_no_revision(jb: Job) -> None:
    three(jb)
    assert jb("notes") == 0
    files = change_files(jb.storage)
    before = memory(jb.storage)
    assert jb("notes") == 0
    assert change_files(jb.storage) == files
    assert memory(jb.storage) == before


def test_notes_does_not_bring_back_a_note_the_synthesizer_changed(jb: Job) -> None:
    three(jb)
    assert jb("notes") == 0
    learned = as_record(router("alpha", "beta", noticed="вивчено синтезатором"))
    hand_change(jb.storage, upsert=[learned])
    files = change_files(jb.storage)
    assert jb("notes") == 0
    assert change_files(jb.storage) == files
    assert memory(jb.storage)["alpha-router"] == learned


def test_notes_after_a_rollback_of_its_revision_brings_nothing_back(jb: Job) -> None:
    three(jb)
    assert jb("notes") == 0
    rollback(jb.storage, 2, "owner", LATER)
    assert memory(jb.storage) == {}
    files = change_files(jb.storage)
    assert jb("notes") == 0
    assert change_files(jb.storage) == files
    assert memory(jb.storage) == {}


def test_notes_after_a_remove_of_one_note_brings_nothing_back(jb: Job) -> None:
    three(jb)
    assert jb("notes") == 0
    hand_change(jb.storage, remove=["beta-router"])
    files = change_files(jb.storage)
    assert jb("notes") == 0
    assert change_files(jb.storage) == files
    assert sorted(memory(jb.storage)) == ["alpha-facilitator", "alpha-router"]


def test_notes_adds_a_new_note_of_the_folder_it_never_published(jb: Job) -> None:
    three(jb)
    assert jb("notes") == 0
    added = facilitator("gamma")
    jb.put("gamma.yaml", [added])
    assert jb("notes") == 0
    record = newest_record(jb.storage)
    assert record.rev == 3 and record.by == "notes"
    view = changes(jb.storage)[0]
    assert view.rev == 3
    assert [r.id for r in view.upserted] == ["gamma-facilitator"]
    assert memory(jb.storage)["gamma-facilitator"] == as_record(added)
    assert sorted(memory(jb.storage)) == [
        "alpha-facilitator",
        "alpha-router",
        "beta-router",
        "gamma-facilitator",
    ]


def test_notes_leaves_the_cards_byte_for_byte(jb: Job) -> None:
    before_files = snapshot(jb.storage, CARDS_PREFIX)
    before_paths = newest_record(jb.storage).cards
    before_cards = current(jb.storage).cards
    three(jb)
    assert jb("notes") == 0
    assert newest_record(jb.storage).rev == 2
    assert snapshot(jb.storage, CARDS_PREFIX) == before_files
    assert newest_record(jb.storage).cards == before_paths
    assert current(jb.storage).cards == before_cards


def test_notes_calls_the_model_only_for_the_vet(jb: Job) -> None:
    three(jb)
    llm = VetLlm()
    jb.use_llm(llm)
    assert jb("notes") == 0
    assert current(jb.storage).rev == 2
    assert llm.streamed == 0
    assert len(llm.calls) >= 1
    assert all(set(call.schema.model_fields) == {"ok", "reason"} for call in llm.calls)


def test_notes_a_refusal_of_the_version_check_logs_notes_rejected_exit_1(
    jb: Job, capsys: pytest.CaptureFixture[str]
) -> None:
    three(jb)
    jb.use_llm(VetLlm(ok=False, reason="ім'я людини: Петро Сидоренко"))
    before = snapshot(jb.storage, "knowledge/")
    capsys.readouterr()
    assert jb("notes") == 1
    out = capsys.readouterr().out
    rejected = events(out, "notes_rejected")
    assert len(rejected) == 1
    assert "Петро Сидоренко" in str(rejected[0])
    assert events(out, "notes_published") == []
    assert snapshot(jb.storage, "knowledge/") == before


class _Answer(BaseModel):
    ok: bool


def _validation_error() -> ValidationError:
    try:
        _Answer.model_validate({})
    except ValidationError as exc:
        return exc
    raise AssertionError("unreachable")


def test_notes_a_model_error_in_the_vet_logs_notes_failed_exit_1_nothing_written(
    jb: Job, capsys: pytest.CaptureFixture[str]
) -> None:
    three(jb)
    for error, name in (
        (LlmUnavailable("модель мовчить"), "LlmUnavailable"),
        (_validation_error(), "ValidationError"),
    ):
        jb.use_llm(VetLlm(error=error))
        before = snapshot(jb.storage, "knowledge/")
        capsys.readouterr()
        assert jb("notes") == 1, name
        out = capsys.readouterr().out
        failed = events(out, "notes_failed")
        assert len(failed) == 1, name
        assert name in str(failed[0]), name
        assert events(out, "notes_published") == [], name
        assert snapshot(jb.storage, "knowledge/") == before, name
        assert current(jb.storage).memory == [], name
