"""Contract tests of the synthesizer: `synthesize` and `runs` (slice tester; from the contract)."""

import re
from collections.abc import Sequence
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from pydantic import BaseModel, ValidationError
from syn_fakes import (
    HEADER,
    NOW,
    RUNS,
    H,
    LogCapture,
    Ob,
    SpyStorage,
    SynthLlm,
    answer,
    change_files,
    change_record,
    hand_apply,
    install_log_capture,
    memory,
    note,
    ok_vet,
    one_obs,
    put_set,
    remove_item,
    run_files,
    run_record,
    seeded,
    upsert_item,
    zero_measure,
)

from thinkhow.knowledge import MemoryRecord, Vet, current, rollback
from thinkhow.learning.synthesize import SYNTHESIZER, SynthesisReport, runs, synthesize
from thinkhow.platform.llm import KnowledgeRev, LlmUnavailable

RUN_FILE = f"{RUNS}20261027T120000Z.json"


@pytest.fixture
def logs(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> LogCapture:
    return install_log_capture(monkeypatch, capsys)


def three(storage: SpyStorage) -> list[Ob]:
    """Two sets of one topic: t1-t2 holds two observations, t3-t4 one; `read_all` order = this list."""
    a = put_set(
        storage,
        [
            Ob("u-a", "tp-1", 1, 2, 1, 1, "знахідка-один", kind="stuck", cause="router", card_id="alpha"),
            Ob("u-a", "tp-1", 1, 2, 2, 2, "знахідка-два", kind="progress", cause="method", card_id="beta"),
        ],
    )
    b = put_set(
        storage,
        [
            Ob(
                "u-a",
                "tp-1",
                3,
                4,
                1,
                3,
                "знахідка-три",
                kind="method_fit",
                cause="circumstances",
                card_id="gamma",
            )
        ],
    )
    return a + b


def go(storage: SpyStorage, llm: SynthLlm, at: datetime = NOW, vet: Vet = ok_vet) -> SynthesisReport:
    return synthesize(storage, llm, at, vet, zero_measure)


def schema_of(storage: SpyStorage, n_obs: int = 2) -> type[BaseModel]:
    """The schema of the one call, captured on a run with `n_obs` new observations."""
    for i in range(n_obs):
        one_obs(storage, f"tp-s{i}", 1, f"для-схеми-{i}")
    llm = SynthLlm()
    go(storage, llm)
    assert len(llm.calls) == 1
    return llm.calls[0].schema


# --- step 2: consumed, nothing_new ------------------------------------------------------------------


def test_nothing_new_without_observations_makes_no_call_and_no_file(tmp_path: Path) -> None:
    storage = seeded(tmp_path)
    llm = SynthLlm()
    before = change_files(storage)
    report = go(storage, llm)
    assert report.outcome == "nothing_new"
    assert report.rev is None
    assert report.considered == 0
    assert llm.calls == []
    assert run_files(storage) == []
    assert change_files(storage) == before


def test_seam1_second_run_on_the_same_files_after_applied_is_nothing_new(tmp_path: Path) -> None:
    storage = seeded(tmp_path)
    o = one_obs(storage, "tp-1", 1, "знахідка")
    llm = SynthLlm([answer(upsert=[upsert_item("n-1", ["o1"])])])
    assert go(storage, llm).outcome == "applied"
    files = run_files(storage)
    changes = change_files(storage)
    second = go(storage, llm, NOW + timedelta(days=1))
    assert second.outcome == "nothing_new"
    assert len(llm.calls) == 1
    assert run_files(storage) == files
    assert change_files(storage) == changes
    assert o.id in change_record(storage, 2).observations


def test_seam1_after_rejected_the_next_run_is_nothing_new(tmp_path: Path) -> None:
    storage = seeded(tmp_path)
    one_obs(storage, "tp-1", 1, "знахідка")
    llm = SynthLlm([answer(remove=[remove_item("no-such-note", ["o1"])])])
    assert go(storage, llm).outcome == "rejected"
    second = go(storage, llm, NOW + timedelta(days=1))
    assert second.outcome == "nothing_new"
    assert len(llm.calls) == 1


def test_seam1_after_no_change_the_next_run_is_nothing_new(tmp_path: Path) -> None:
    storage = seeded(tmp_path)
    one_obs(storage, "tp-1", 1, "знахідка")
    llm = SynthLlm([answer()])
    assert go(storage, llm).outcome == "no_change"
    second = go(storage, llm, NOW + timedelta(days=1))
    assert second.outcome == "nothing_new"
    assert len(llm.calls) == 1


def test_seam1_after_failed_the_next_run_feeds_the_same_ids(tmp_path: Path) -> None:
    storage = seeded(tmp_path)
    obs = three(storage)
    llm = SynthLlm([LlmUnavailable("down"), answer(upsert=[upsert_item("n-1", ["o1", "o2", "o3"])])])
    assert go(storage, llm).outcome == "failed"
    assert run_files(storage) == []
    second = go(storage, llm, NOW + timedelta(days=1))
    assert second.outcome == "applied"
    assert second.considered == 3
    assert len(llm.calls) == 2
    for o in obs:
        assert o.finding in llm.calls[0].text
        assert o.finding in llm.calls[1].text
    assert set(change_record(storage, 2).observations) == {o.id for o in obs}


def test_consumed_includes_the_observations_of_every_change_record(tmp_path: Path) -> None:
    storage = seeded(tmp_path)
    cited = one_obs(storage, "tp-1", 1, "знахідка-процитована-руками")
    fresh = one_obs(storage, "tp-2", 1, "знахідка-свіжа")
    hand_apply(storage, upsert=[note("m-hand")], observations=[cited.id])
    llm = SynthLlm([answer(upsert=[upsert_item("n-1", ["o1"])])])
    report = go(storage, llm)
    assert report.outcome == "applied"
    assert report.considered == 1
    text = llm.calls[0].text
    assert "знахідка-свіжа" in text
    assert "знахідка-процитована-руками" not in text
    assert change_record(storage, report.rev).observations == [fresh.id]
    assert run_record(storage, RUN_FILE)["considered"] == [fresh.id]


# --- step 3: the one call and its text --------------------------------------------------------------


def test_one_generate_json_call_with_the_synthesizer_instruction_one_user_turn_and_the_rev_pair(
    tmp_path: Path,
) -> None:
    storage = seeded(tmp_path)
    hand_apply(storage, upsert=[note("m-a")])  # rev 2
    one_obs(storage, "tp-1", 1, "знахідка")
    now = current(storage)
    llm = SynthLlm([answer()])
    go(storage, llm)
    assert len(llm.calls) == 1
    call = llm.calls[0]
    assert call.system == SYNTHESIZER
    assert len(call.contents) == 1
    assert call.contents[0].role == "user"
    assert call.rev == KnowledgeRev(rev=now.rev, n=now.n)


def test_the_text_has_every_card_id_method_and_title_and_no_phase(tmp_path: Path) -> None:
    storage = seeded(tmp_path)
    one_obs(storage, "tp-1", 1, "знахідка")
    llm = SynthLlm([answer()])
    go(storage, llm)
    text = llm.calls[0].text
    for cid, title in {"alpha": "Альфа", "beta": "Бета", "gamma": "Гамма"}.items():
        assert cid in text
        assert f"Метод-{cid}" in text
        assert title in text
        for word in ("фазаназва", "фазамета", "фазахід", "фазавихід"):
            assert f"{word}-{cid}" not in text


def test_the_text_has_every_current_note_with_id_audience_cards_title_noticed_do(tmp_path: Path) -> None:
    storage = seeded(tmp_path)
    hand_apply(
        storage,
        upsert=[
            note("m-route", cards=["beta"], audience="router", noticed="помічено-роутер", do="робити-роутер"),
            note("m-fac", cards=["gamma"], audience="facilitator", noticed="помічено-фас", do="робити-фас"),
        ],
    )
    one_obs(storage, "tp-1", 1, "знахідка")
    llm = SynthLlm([answer()])
    go(storage, llm)
    text = llm.calls[0].text
    for token in (
        "m-route",
        "router",
        "заголовок m-route",
        "помічено-роутер",
        "робити-роутер",
        "m-fac",
        "facilitator",
        "заголовок m-fac",
        "помічено-фас",
        "робити-фас",
        "beta",
        "gamma",
    ):
        assert token in text, token


def test_the_text_has_each_new_observation_with_alias_card_kind_cause_finding(tmp_path: Path) -> None:
    storage = seeded(tmp_path)
    obs = three(storage)
    llm = SynthLlm([answer()])
    go(storage, llm)
    text = llm.calls[0].text
    for k, o in enumerate(obs, start=1):
        assert re.search(rf"(?<![A-Za-z0-9])o{k}(?![0-9])", text), f"o{k}"
        assert o.finding in text
        assert o.kind in text
        assert o.cause in text
        assert o.card_id is not None and o.card_id in text


def test_seam2_a_rolled_back_change_is_in_the_text_under_its_header(tmp_path: Path) -> None:
    storage = seeded(tmp_path)
    rev = hand_apply(
        storage,
        upsert=[note("m-bad", noticed="відкочене-помічено", do="відкочене-робити")],
        what="погана зміна",
    )
    rollback(storage, rev, by="owner@example.com", now=NOW - H)
    assert "m-bad" not in memory(storage)
    one_obs(storage, "tp-1", 1, "знахідка")
    llm = SynthLlm([answer()])
    go(storage, llm)
    text = llm.calls[0].text
    assert HEADER in text
    after = text[text.index(HEADER) :]
    assert "відкочене-помічено" in after
    assert "відкочене-робити" in after


def test_seam2_a_rollback_that_changed_nothing_is_not_in_the_text(tmp_path: Path) -> None:
    storage = seeded(tmp_path)
    first = hand_apply(storage, upsert=[note("m-1", noticed="перша-версія-помічено")])  # rev 2
    hand_apply(storage, upsert=[note("m-1", noticed="друга-версія-помічено")])  # rev 3 replaces it
    rollback(storage, first, by="owner@example.com", now=NOW - H)  # acts on nothing: rev 3 wins
    assert memory(storage)["m-1"].noticed == "друга-версія-помічено"
    one_obs(storage, "tp-1", 1, "знахідка")
    llm = SynthLlm([answer()])
    go(storage, llm)
    text = llm.calls[0].text
    assert HEADER not in text
    assert "перша-версія-помічено" not in text


# --- step 4: the schema -----------------------------------------------------------------------------


def test_schema_cards_are_an_enum_of_the_current_cards_at_least_one(tmp_path: Path) -> None:
    schema = schema_of(seeded(tmp_path), n_obs=1)
    schema.model_validate(answer(upsert=[upsert_item("n-1", ["o1"], cards=["alpha", "beta", "gamma"])]))
    for bad in (["zeta"], [], ["alpha", "zeta"]):
        with pytest.raises(ValidationError):
            schema.model_validate(answer(upsert=[upsert_item("n-1", ["o1"], cards=bad)]))


def test_schema_citations_are_an_enum_of_o1_to_oN_at_least_one(tmp_path: Path) -> None:
    schema = schema_of(seeded(tmp_path), n_obs=2)
    schema.model_validate(
        answer(upsert=[upsert_item("n-1", ["o1", "o2"])], remove=[remove_item("x-1", ["o2", "o1"])])
    )
    for bad in (["o3"], [], ["o0"], ["o1", "o3"]):
        with pytest.raises(ValidationError):
            schema.model_validate(answer(upsert=[upsert_item("n-1", bad)]))
        with pytest.raises(ValidationError):
            schema.model_validate(answer(remove=[remove_item("x-1", bad)]))


def test_schema_ids_audience_and_empty_lists(tmp_path: Path) -> None:
    schema = schema_of(seeded(tmp_path), n_obs=1)
    schema.model_validate(answer())  # both lists empty
    longest = "A" * 63 + "9"
    schema.model_validate(
        answer(
            upsert=[upsert_item(longest, ["o1"], audience="router"), upsert_item("Ab-9", ["o1"])],
            remove=[remove_item("not-in-memory-at-all", ["o1"])],  # remove[].id has no enum
        )
    )
    for bad_id in ("bad id", "a_b", "", "A" * 65, "ї"):
        with pytest.raises(ValidationError):
            schema.model_validate(answer(upsert=[upsert_item(bad_id, ["o1"])]))
        with pytest.raises(ValidationError):
            schema.model_validate(answer(remove=[remove_item(bad_id, ["o1"])]))
    with pytest.raises(ValidationError):
        schema.model_validate(answer(upsert=[upsert_item("n-1", ["o1"], audience="owner")]))


def test_seam3_the_enum_holds_only_the_aliases_of_new_a_foreign_alias_fails(tmp_path: Path) -> None:
    storage = seeded(tmp_path)
    one_obs(storage, "tp-1", 1, "стара-1")
    one_obs(storage, "tp-2", 1, "стара-2")
    llm = SynthLlm([answer(upsert=[upsert_item("n-1", ["o1", "o2"])])])
    assert go(storage, llm).outcome == "applied"
    one_obs(storage, "tp-3", 1, "нова")
    changes = change_files(storage)
    runs_before = run_files(storage)
    llm.plan.append(answer(upsert=[upsert_item("n-2", ["o2"])]))  # o2 is not an alias of this run
    report = go(storage, llm, NOW + timedelta(days=1))
    assert report.outcome == "failed"
    assert change_files(storage) == changes
    assert run_files(storage) == runs_before


def test_aliases_follow_read_all_order_and_map_back_to_the_full_ids(tmp_path: Path) -> None:
    storage = seeded(tmp_path)
    obs = three(storage)
    llm = SynthLlm([answer(upsert=[upsert_item("n-1", ["o2"])])])
    report = go(storage, llm)
    assert report.outcome == "applied"
    assert change_record(storage, report.rev).observations == [obs[1].id]


def test_aliases_of_a_later_run_count_from_o1_over_its_new_observations(tmp_path: Path) -> None:
    storage = seeded(tmp_path)
    one_obs(storage, "tp-1", 1, "стара")
    llm = SynthLlm([answer(upsert=[upsert_item("n-1", ["o1"])])])
    go(storage, llm)
    new = one_obs(storage, "tp-2", 1, "нова")
    llm.plan.append(answer(upsert=[upsert_item("n-2", ["o1"])]))
    report = go(storage, llm, NOW + timedelta(days=1))
    assert report.outcome == "applied"
    assert change_record(storage, report.rev).observations == [new.id]


def test_seam3_first_run_after_seed_with_empty_memory_applies_an_upsert(tmp_path: Path) -> None:
    storage = seeded(tmp_path)
    assert current(storage).memory == []
    one_obs(storage, "tp-1", 1, "знахідка")
    llm = SynthLlm([answer(upsert=[upsert_item("n-1", ["o1"])])])
    report = go(storage, llm)
    assert report.outcome == "applied"
    assert report.rev == 2
    assert current(storage).rev == 2
    assert set(memory(storage)) == {"n-1"}


def test_seam3_remove_of_an_unknown_id_is_rejected_without_raising(tmp_path: Path) -> None:
    storage = seeded(tmp_path)
    o = one_obs(storage, "tp-1", 1, "знахідка")
    llm = SynthLlm([answer(remove=[remove_item("no-such-note", ["o1"])])])
    changes = change_files(storage)
    report = go(storage, llm)
    assert report.outcome == "rejected"
    assert report.rev is None
    assert change_files(storage) == changes
    record = run_record(storage, RUN_FILE)
    assert record["outcome"] == "rejected"
    assert record["considered"] == [o.id]
    assert isinstance(record["rejected"], str) and record["rejected"]


# --- step 5: the change -----------------------------------------------------------------------------


def test_both_lists_empty_is_no_change_with_a_run_record_and_no_revision(tmp_path: Path) -> None:
    storage = seeded(tmp_path)
    obs = three(storage)
    llm = SynthLlm([answer()])
    report = go(storage, llm)
    assert report.outcome == "no_change"
    assert report.rev is None
    assert report.considered == 3
    assert current(storage).rev == 1
    assert change_files(storage) == ["knowledge/changes/000001.json"]
    record = run_record(storage, RUN_FILE)
    assert record["outcome"] == "no_change"
    assert record["rev"] is None
    assert sorted(record["considered"]) == sorted(o.id for o in obs)


def test_the_change_carries_what_why_by_synthesizer_and_the_notes_of_the_answer(tmp_path: Path) -> None:
    storage = seeded(tmp_path)
    o = one_obs(storage, "tp-1", 1, "знахідка")
    item = upsert_item(
        "n-1", ["o1"], cards=["beta", "gamma"], audience="router", title="Т", noticed="П", do="Р"
    )
    llm = SynthLlm([answer(upsert=[item], what="що-зроблено", why="чому-зроблено")])
    report = go(storage, llm)
    assert report.outcome == "applied"
    record = change_record(storage, report.rev)
    assert record.what == "що-зроблено"
    assert record.why == "чому-зроблено"
    assert record.by == "synthesizer"
    assert memory(storage)["n-1"] == MemoryRecord(
        id="n-1",
        title="Т",
        cards=["beta", "gamma"],
        noticed="П",
        do="Р",
        basis=f"спостереження: {o.id}",
        audience="router",
    )


def test_the_change_cites_every_observation_its_upserts_and_removes_cite(tmp_path: Path) -> None:
    storage = seeded(tmp_path)
    hand_apply(storage, upsert=[note("m-old")])
    obs = three(storage)
    llm = SynthLlm([answer(upsert=[upsert_item("n-1", ["o1"])], remove=[remove_item("m-old", ["o3"])])])
    report = go(storage, llm)
    assert report.outcome == "applied"
    assert set(change_record(storage, report.rev).observations) == {obs[0].id, obs[2].id}
    assert set(memory(storage)) == {"n-1"}


def test_basis_of_a_new_note_is_the_cited_full_ids(tmp_path: Path) -> None:
    storage = seeded(tmp_path)
    obs = three(storage)
    llm = SynthLlm([answer(upsert=[upsert_item("n-1", ["o3", "o1"])])])
    assert go(storage, llm).outcome == "applied"
    basis = memory(storage)["n-1"].basis
    prefix = "спостереження: "
    assert basis.startswith(prefix), basis
    assert set(basis[len(prefix) :].split(", ")) == {obs[0].id, obs[2].id}


def test_basis_of_an_existing_note_keeps_its_basis_and_adds_the_cited_ids(tmp_path: Path) -> None:
    storage = seeded(tmp_path)
    hand_apply(storage, upsert=[note("m-a", basis="стартове джерело S5")])
    obs = three(storage)
    llm = SynthLlm([answer(upsert=[upsert_item("m-a", ["o2"])])])
    assert go(storage, llm).outcome == "applied"
    assert memory(storage)["m-a"].basis == f"стартове джерело S5; спостереження: {obs[1].id}"


# --- step 6: apply_memory's answers -----------------------------------------------------------------


def test_apply_memory_none_is_no_change(tmp_path: Path) -> None:
    storage = seeded(tmp_path)
    o = one_obs(storage, "tp-1", 1, "знахідка")
    storage.forced = ("knowledge/changes/", False)  # another run created the change record first
    llm = SynthLlm([answer(upsert=[upsert_item("n-1", ["o1"])])])
    report = go(storage, llm)
    assert report.outcome == "no_change"
    assert report.rev is None
    record = run_record(storage, RUN_FILE)
    assert record["outcome"] == "no_change"
    assert record["considered"] == [o.id]


def test_a_version_check_refusal_is_rejected_with_its_reason_in_the_run_record(tmp_path: Path) -> None:
    storage = seeded(tmp_path)
    o = one_obs(storage, "tp-1", 1, "знахідка")
    llm = SynthLlm([answer(upsert=[upsert_item("n-1", ["o1"])])])

    def vet(records: Sequence[MemoryRecord]) -> str | None:
        return "названо місто людини"

    report = go(storage, llm, vet=vet)
    assert report.outcome == "rejected"
    assert report.rev is None
    assert current(storage).rev == 1
    record = run_record(storage, RUN_FILE)
    assert record["outcome"] == "rejected"
    assert record["rev"] is None
    assert record["considered"] == [o.id]
    assert "подробиці людей" in record["rejected"]
    assert "названо місто людини" in record["rejected"]


# --- step 7: the run record, failures, logs ---------------------------------------------------------


def test_the_run_record_is_named_by_now_and_holds_at_considered_outcome_rev(tmp_path: Path) -> None:
    storage = seeded(tmp_path)
    obs = three(storage)
    llm = SynthLlm([answer(upsert=[upsert_item("n-1", ["o1"])])])
    report = go(storage, llm)
    assert report.outcome == "applied"
    assert run_files(storage) == [RUN_FILE]
    record = run_record(storage, RUN_FILE)
    assert record["outcome"] == "applied"
    assert record["rev"] == report.rev == 2
    assert record["rejected"] is None
    assert sorted(record["considered"]) == sorted(o.id for o in obs)
    assert record["at"].startswith("2026-10-27T12:00:00")
    assert ("system", RUN_FILE) in storage.writes


def test_a_taken_run_name_gets_the_suffix_2_then_3(tmp_path: Path) -> None:
    storage = seeded(tmp_path)
    llm = SynthLlm()
    for i in range(3):
        one_obs(storage, f"tp-{i}", 1, f"знахідка-{i}")
        assert go(storage, llm).outcome == "no_change"
    assert set(run_files(storage)) == {
        f"{RUNS}20261027T120000Z.json",
        f"{RUNS}20261027T120000Z-2.json",
        f"{RUNS}20261027T120000Z-3.json",
    }


def test_the_model_unavailable_is_failed_with_no_run_record_and_no_change(tmp_path: Path) -> None:
    storage = seeded(tmp_path)
    one_obs(storage, "tp-1", 1, "знахідка")
    llm = SynthLlm([LlmUnavailable("down")])
    report = go(storage, llm)
    assert report.outcome == "failed"
    assert report.rev is None
    assert run_files(storage) == []
    assert change_files(storage) == ["knowledge/changes/000001.json"]


def test_a_model_error_inside_vet_is_failed_with_no_run_record(tmp_path: Path) -> None:
    storage = seeded(tmp_path)
    one_obs(storage, "tp-1", 1, "знахідка")

    def vet(records: Sequence[MemoryRecord]) -> str | None:
        raise LlmUnavailable("vet down")

    llm = SynthLlm([answer(upsert=[upsert_item("n-1", ["o1"])])])
    report = go(storage, llm, vet=vet)
    assert report.outcome == "failed"
    assert run_files(storage) == []
    assert current(storage).rev == 1


def test_a_failure_logs_synthesize_failed_with_the_error_type(tmp_path: Path, logs: LogCapture) -> None:
    storage = seeded(tmp_path)
    one_obs(storage, "tp-1", 1, "знахідка")
    go(storage, SynthLlm([LlmUnavailable("down")]))
    failed = logs.events("synthesize_failed")
    assert len(failed) == 1
    assert "LlmUnavailable" in [str(v) for v in failed[0].values()]


def test_synthesize_done_logs_outcome_rev_considered_without_text(tmp_path: Path, logs: LogCapture) -> None:
    storage = seeded(tmp_path)
    one_obs(storage, "tp-1", 1, "знахідка-секретна")
    llm = SynthLlm(
        [answer(upsert=[upsert_item("n-1", ["o1"], noticed="помічено-секретне")], what="що-секретне")]
    )
    go(storage, llm)
    done = logs.events("synthesize_done")
    assert len(done) == 1
    line = done[0]
    assert line["outcome"] == "applied"
    assert line["rev"] == 2
    assert "considered" in line
    raw = str(line)
    for secret in ("знахідка-секретна", "помічено-секретне", "що-секретне"):
        assert secret not in raw


def test_the_report_has_rev_considered_count_and_outcome(tmp_path: Path) -> None:
    storage = seeded(tmp_path)
    three(storage)
    llm = SynthLlm([answer(upsert=[upsert_item("n-1", ["o1"])])])
    report = go(storage, llm)
    assert (report.rev, report.considered, report.outcome) == (2, 3, "applied")


def test_runs_reads_every_run_record_in_name_order(tmp_path: Path) -> None:
    storage = seeded(tmp_path)
    first = one_obs(storage, "tp-1", 1, "знахідка-1")
    llm = SynthLlm([answer(), answer(upsert=[upsert_item("n-1", ["o1"])])])
    go(storage, llm, NOW)
    second = one_obs(storage, "tp-2", 1, "знахідка-2")
    go(storage, llm, NOW + timedelta(days=1))
    got = runs(storage)
    assert [(r.outcome, r.rev, r.considered, r.rejected) for r in got] == [
        ("no_change", None, [first.id], None),
        ("applied", 2, [second.id], None),
    ]
    assert [r.at for r in got] == [NOW, NOW + timedelta(days=1)]


def test_synthesize_does_not_read_the_users_bucket(tmp_path: Path) -> None:
    storage = seeded(tmp_path)
    one_obs(storage, "tp-1", 1, "знахідка")
    storage.reset()
    go(storage, SynthLlm([answer(upsert=[upsert_item("n-1", ["o1"])])]))
    assert [r for r in storage.reads if r[0] == "users"] == []
    assert [r for r in storage.lists if r[0] == "users"] == []
