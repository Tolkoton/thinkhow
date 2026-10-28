"""Block tests of learning-loop (task 309): one per line of «Inter-slice contracts».

Slice tester, mode `block`; from `.engine/architecture/feature/learning-loop.md`, the slice contracts it names
and the public signatures, not the bodies. Every test drives at least two slices together through their public
seams (workspace → analyzer → synthesizer → Knowledge → readers → web). Expected values are written by hand.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from ll_fakes import (
    ALICE,
    CARDS,
    DAY,
    H_OWNER,
    HEADER,
    NOTES,
    OWNER,
    STEP,
    T0,
    Clock,
    Facil,
    H,
    Q,
    Rec,
    ScenarioLlm,
    analyzer_says,
    local_environ,
    make_client,
    memory_of,
    ok_vet,
    outcome,
    page,
    put_raw,
    say,
    seeded,
    synth_says,
    system_files,
    system_json,
    upsert_item,
    with_chosen_step,
    write_cards,
    zero_measure,
)

from thinkhow import knowledge
from thinkhow.facilitation import recognize_step
from thinkhow.facilitation.respond import system_instruction
from thinkhow.facilitation.route import router_instruction
from thinkhow.facilitation.types import StepOutcome
from thinkhow.knowledge import BUDGET_CHARS, changes, current, publish, read_notes, rollback
from thinkhow.learning import job
from thinkhow.learning.analyze import analyze
from thinkhow.learning.observations import read_all
from thinkhow.learning.synthesize import runs, synthesize
from thinkhow.learning.vet import measure
from thinkhow.platform.storage import LocalStorage
from thinkhow.web.app import build_deps
from thinkhow.workspace import TopicRef, reply, step_results_for_learning


def observe(storage: LocalStorage, at: datetime, finding: str = "людина застрягла") -> str:
    """A new topic (turns #1, #2 at `at`), analyzed an hour later: the id of its one observation."""
    ref = with_chosen_step(storage, at)
    report = analyze(storage, ScenarioLlm(analyzer_says(anchor="t1", finding=finding)), at + H)
    assert report.written == 1, report
    return f"{ref.uid}/{ref.topic_id}/t1-t2/1"


def synth(storage: LocalStorage, at: datetime, *items: dict[str, object]) -> int:
    report = synthesize(storage, ScenarioLlm(synth_says(*items)), at, ok_vet, zero_measure)
    assert report.outcome == "applied", report
    assert report.rev is not None
    return report.rev


# S1 → S3, S5: MemoryChange → apply_memory writes knowledge/memory/<id>/v<N>.json + changes/<rev+1>.json
# (cards — the same dict as in the previous record; observations — the ids of observations)
def test_s1_to_s3_the_synthesizers_change_writes_a_memory_version_and_a_record_with_same_cards_and_ids(
    tmp_path: Path,
) -> None:
    storage = seeded(tmp_path)
    obs_id = observe(storage, T0)
    assert [o.id for o in read_all(storage)] == [obs_id]

    rev = synth(storage, T0 + 2 * H, upsert_item("n-one", cards=["beta"]))

    assert rev == 2
    assert system_files(storage, "knowledge/memory/n-one/") == ["knowledge/memory/n-one/v1.json"]
    first = system_json(storage, "knowledge/changes/000001.json")
    second = system_json(storage, "knowledge/changes/000002.json")
    assert second["cards"] == first["cards"]
    assert second["observations"] == [obs_id]
    assert second["by"] == "synthesizer"
    assert str(second["memory"]["n-one"]).endswith("n-one/v1.json")
    note = memory_of(storage)["n-one"]
    assert (note.cards, note.noticed, note.do) == (["beta"], "помічено n-one", "робити n-one")


# S1 → S3: a rejected version is seen in the feed — the synthesizer writes the reason into the run record
# learning/synthesis/<час>.json, and /learning shows it as «відхилено перевіркою: <причина>»
def test_s1_to_s3_a_vet_refusal_lands_in_the_run_record_and_on_the_learning_page(tmp_path: Path) -> None:
    storage = seeded(tmp_path)
    obs_id = observe(storage, T0)
    reason = "у нотатці ім'я людини"

    report = synthesize(
        storage,
        ScenarioLlm(synth_says(upsert_item("n-bad"))),
        T0 + 2 * H,
        lambda records: reason,
        zero_measure,
    )

    assert report.outcome == "rejected"
    assert system_files(storage, "knowledge/changes/") == ["knowledge/changes/000001.json"]
    (run,) = runs(storage)
    assert (run.outcome, run.considered) == ("rejected", [obs_id])
    assert run.rejected is not None and reason in run.rejected  # the vet's reason, maybe under its category
    text = page(make_client(tmp_path, storage, Clock(T0 + 3 * H)), "/learning", H_OWNER)
    assert f"відхилено перевіркою: {run.rejected}" in text


# S1 → S5: `job notes` puts the starting notes through apply_memory: one revision, the cards dict the same
def test_s1_to_s5_job_notes_writes_one_revision_of_memory_only(tmp_path: Path) -> None:
    root = tmp_path / "local"
    env = local_environ(root)
    assert job.run(["seed"], env, CARDS, lambda: T0) == 0
    storage = LocalStorage(root)
    before = current(storage)

    assert job.run(["notes"], env, CARDS, lambda: T0 + H) == 0

    after = current(storage)
    assert after.rev == before.rev + 1
    first = system_json(storage, f"knowledge/changes/{before.rev:06d}.json")
    second = system_json(storage, f"knowledge/changes/{after.rev:06d}.json")
    assert second["cards"] == first["cards"]
    assert sorted(second["memory"]) == sorted(r.id for r in read_notes(NOTES))
    assert {r.id: r for r in after.memory} == {r.id: r for r in read_notes(NOTES)}


# ChangeRecord gets the optional fields observations: list[str] = [], by: str = "" (old records are read)
def test_an_old_change_record_without_the_new_fields_is_read_by_the_synthesizer_the_feed_and_the_page(
    tmp_path: Path,
) -> None:
    storage = seeded(tmp_path)
    path = "knowledge/changes/000001.json"
    old = system_json(storage, path)
    for key in ("observations", "by", "replaced"):
        old.pop(key, None)
    LocalStorage.write(storage, "system", path, json.dumps(old).encode(), "application/json")
    observe(storage, T0)

    assert synth(storage, T0 + 2 * H, upsert_item("n-one")) == 2

    seed_view = next(v for v in changes(storage) if v.rev == 1)
    assert (seed_view.observations, seed_view.by) == ([], "")
    assert "n-one" in page(make_client(tmp_path, storage, Clock(T0 + 3 * H)), "/learning", H_OWNER)


# S1 → S3 (rollback): Rollback(...) in knowledge/rollbacks/<n>.json; a second rollback of the same rev —
# refused (AlreadyRolledBack); the page's POST /learning/rollback/{rev}
def test_s1_to_s3_the_owner_rolls_back_over_the_page_and_a_second_rollback_is_refused(tmp_path: Path) -> None:
    storage = seeded(tmp_path)
    observe(storage, T0)
    rev = synth(storage, T0 + 2 * H, upsert_item("n-one"))
    client = make_client(tmp_path, storage, Clock(T0 + 3 * H))

    r = client.post(f"/learning/rollback/{rev}", headers=H_OWNER)

    assert r.status_code == 303 and r.headers["location"].endswith("/learning")
    assert system_files(storage, "knowledge/rollbacks/") == ["knowledge/rollbacks/000001.json"]
    record = system_json(storage, "knowledge/rollbacks/000001.json")
    assert (record["n"], record["rev"], record["by"]) == (1, rev, OWNER.email)
    assert "n-one" not in memory_of(storage)
    assert current(storage).n == 1
    assert client.post(f"/learning/rollback/{rev}", headers=H_OWNER).status_code == 409
    assert system_files(storage, "knowledge/rollbacks/") == ["knowledge/rollbacks/000001.json"]


# a rollback after which no id changed (all already replaced by later revisions) is written, and the feed
# says «нічого не змінено»
def test_a_rollback_of_a_change_whose_note_a_later_revision_replaced_is_written_and_changes_nothing(
    tmp_path: Path,
) -> None:
    storage = seeded(tmp_path)
    observe(storage, T0)
    old = synth(storage, T0 + 2 * H, upsert_item("n-x", noticed="перша версія"))
    observe(storage, T0 + DAY)
    synth(storage, T0 + DAY + 2 * H, upsert_item("n-x", noticed="друга версія"))

    assert rollback(storage, old, OWNER.email, T0 + DAY + 3 * H) == 1

    assert system_files(storage, "knowledge/rollbacks/") == ["knowledge/rollbacks/000001.json"]
    assert memory_of(storage)["n-x"].noticed == "друга версія"
    view = next(v for v in changes(storage) if v.rev == old)
    assert (view.rolled_back, view.rollback_changed) == (1, [])
    text = page(make_client(tmp_path, storage, Clock(T0 + DAY + 4 * H)), "/learning", H_OWNER)
    assert "нічого не змінено" in text


# A new revision is built from current() after the rollbacks — both in apply_memory and in publish()
def test_after_a_rollback_neither_the_next_synthesis_nor_publish_brings_the_rolled_back_note_back(
    tmp_path: Path,
) -> None:
    cards_dir = write_cards(tmp_path / "cards")
    storage = seeded(tmp_path, cards_dir)
    observe(storage, T0)
    rev = synth(storage, T0 + 2 * H, upsert_item("n-x"))
    rollback(storage, rev, OWNER.email, T0 + 3 * H)
    observe(storage, T0 + DAY)

    synth(storage, T0 + DAY + 2 * H, upsert_item("n-y"))
    assert sorted(memory_of(storage)) == ["n-y"]

    alpha = cards_dir / "alpha.yaml"
    alpha.write_text(alpha.read_text(encoding="utf-8").replace("Альфа", "Альфа нова"), encoding="utf-8")
    published = publish(storage, cards_dir)
    assert published is not None
    assert current(storage).rev == published
    assert current(storage).cards["alpha"].title == "Альфа нова"
    assert sorted(memory_of(storage)) == ["n-y"]
    assert sorted(system_json(storage, f"knowledge/changes/{published:06d}.json")["memory"]) == ["n-y"]


# knowledge.changes → ChangeView(... rolled_back ...): the rolled-back content (upserted, removed) the
# synthesizer gets as «не пропонуй знову»
def test_the_synthesizer_is_given_the_rolled_back_note_under_do_not_propose_again(tmp_path: Path) -> None:
    storage = seeded(tmp_path)
    observe(storage, T0)
    rev = synth(storage, T0 + 2 * H, upsert_item("n-x", noticed="відкочене-помічене-слово"))
    rollback(storage, rev, OWNER.email, T0 + 3 * H)
    observe(storage, T0 + DAY)
    llm = ScenarioLlm(synth_says())

    synthesize(storage, llm, T0 + DAY + 2 * H, ok_vet, zero_measure)

    (call,) = llm.calls
    assert HEADER in call.text
    assert "відкочене-помічене-слово" in call.text[call.text.index(HEADER) :]
    assert next(v for v in changes(storage) if v.rev == rev).rolled_back == 1


# S1 → S4: MemoryRecord.audience: Literal["router", "facilitator"]; cards — the ids of the cards the record is
# about (the router sees the router notes by each card, the facilitator the facilitator notes of its card)
def test_s1_to_s4_a_router_note_and_a_facilitator_note_reach_only_their_readers(tmp_path: Path) -> None:
    storage = seeded(tmp_path)
    observe(storage, T0)
    synth(
        storage,
        T0 + 2 * H,
        upsert_item("n-r", cards=["alpha"], audience="router", noticed="роутер-досвід-слово"),
        upsert_item("n-f", cards=["beta"], audience="facilitator", noticed="фасилітатор-досвід-слово"),
    )
    now = current(storage)

    router = router_instruction(now, None)
    assert "Досвід:" in router
    assert "- назва n-r. роутер-досвід-слово робити n-r" in router
    assert "фасилітатор-досвід-слово" not in router
    beta = system_instruction(now.cards["beta"], now.memory)
    assert "фасилітатор-досвід-слово" in beta and "роутер-досвід-слово" not in beta
    alpha = system_instruction(now.cards["alpha"], now.memory)
    assert "фасилітатор-досвід-слово" not in alpha and "роутер-досвід-слово" not in alpha


# S2 → S3: learning/observations/<uid>/<topic>/t<a>-t<b>.json = ObservationSet(...); an old file (one
# observation) is read as a set of one; an old s<n>.json the same. Reader: read_all
def test_s2_to_s3_the_synthesizer_takes_the_new_set_and_both_old_shapes_through_read_all(
    tmp_path: Path,
) -> None:
    storage = seeded(tmp_path)
    put_raw(
        storage,
        "alice-1",
        "aaa111",
        "s2.json",
        '{"uid":"alice-1","topic_id":"aaa111","session_no":2,"turn":2,"link":"/topics/alice-1/aaa111#t2",'
        '"worked":false,"finding":"стара-сесія-знахідка","cause":"circumstances",'
        '"closed_at":"2026-10-19T03:00:00Z","analyzed_at":"2026-10-19T04:00:00Z"}',
    )
    put_raw(
        storage,
        "alice-1",
        "aaa111",
        "t3-t4.json",
        '{"uid":"alice-1","topic_id":"aaa111","first_turn":3,"last_turn":4,"turn":4,'
        '"link":"/topics/alice-1/aaa111#t4","worked":true,"finding":"старий-діапазон-знахідка",'
        '"cause":"facilitation","analyzed_at":"2026-10-19T05:00:00Z"}',
    )
    new_id = observe(storage, T0, finding="новий-набір-знахідка")
    llm = ScenarioLlm(synth_says(upsert_item("n-one", observations=["o1", "o2", "o3"])))

    report = synthesize(storage, llm, T0 + 2 * H, ok_vet, zero_measure)

    assert report.outcome == "applied" and report.considered == 3
    expected = {"alice-1/aaa111/s2/1", "alice-1/aaa111/t3-t4/1", new_id}
    assert set(runs(storage)[0].considered) == expected
    record = system_json(storage, "knowledge/changes/000002.json")
    assert set(record["observations"]) == expected
    (call,) = llm.calls
    for finding in ("стара-сесія-знахідка", "старий-діапазон-знахідка", "новий-набір-знахідка"):
        assert finding in call.text


# S6 changes the analyzer: the results of steps go into the analyzer's input, `kind: step` fills S6;
# step_results_for_learning; the analyzer gives the results without `clearer`
def test_s6_to_s2_to_s3_a_step_result_reaches_the_analyzer_without_clearer_and_then_the_synthesizer(
    tmp_path: Path,
) -> None:
    storage = seeded(tmp_path)
    ref = with_chosen_step(storage, T0)
    say(
        storage,
        ref,
        "Вийшло: поговорив з трьома",
        T0 + DAY,
        recognize=Rec(outcome("worked", "no", "двоє за")),
    )
    assert [(r.outcome, r.clearer) for r in step_results_for_learning(storage, ref)] == [("worked", "no")]
    analyzer = ScenarioLlm(analyzer_says(kind="step", anchor="t4", finding="крок-спостереження"))

    analyze(storage, analyzer, T0 + DAY + H)

    (call,) = analyzer.calls
    lines = call.lines()
    person = lines.index("#4 людина: Вийшло: поговорив з трьома")
    assert lines[person - 1] == f"[Результат кроку «{STEP}»: вийшло — двоє за]"
    assert "ясніше" not in call.text
    (obs,) = read_all(storage)
    assert (obs.id, obs.kind, obs.turn) == (f"{ref.uid}/{ref.topic_id}/t1-t5/1", "step", 4)
    synthesizer = ScenarioLlm(synth_says())
    synthesize(storage, synthesizer, T0 + DAY + 2 * H, ok_vet, zero_measure)
    (seen,) = synthesizer.calls
    assert "крок-спостереження" in seen.text and "step" in seen.text


# the seam facilitation.recognize_step(step, question, text, llm) -> StepOutcome | None, which workspace.reply
# gets by injection, like facilitate
def test_recognize_step_injected_into_reply_writes_the_result_into_steps_json(tmp_path: Path) -> None:
    storage = seeded(tmp_path)
    ref: TopicRef = with_chosen_step(storage, T0)
    llm = ScenarioLlm(
        lambda schema: {
            "answered": True,
            "outcome": "not_worked",
            "clearer": "partly",
            "said": "ніхто не прийшов",
        }
    )

    def recognize(step: str, question: str, text: str) -> StepOutcome:
        return recognize_step(step, question, text, llm)

    list(
        reply(
            storage,
            Facil(),
            ALICE,
            ref,
            "Ніхто не прийшов на зустріч",
            T0 + DAY,
            recognize=recognize,
            question=Q,
        )
    )

    (result,) = step_results_for_learning(storage, ref)
    assert (result.step, result.outcome, result.clearer, result.said) == (
        STEP,
        "not_worked",
        "partly",
        "ніхто не прийшов",
    )
    (call,) = llm.calls
    assert "Ніхто не прийшов на зустріч" in call.text
    deps = build_deps(local_environ(tmp_path / "local"), write_cards(tmp_path / "cards2"))
    assert deps.recognize is not None


# refined by S1: apply_memory(storage, change, vet, measure) -> int | None; measure — the budget injected from
# learning/vet.py
def test_the_synthesizers_note_over_the_budget_of_learning_vet_measure_is_rejected(tmp_path: Path) -> None:
    storage = seeded(tmp_path)
    observe(storage, T0)
    huge = "ж" * (BUDGET_CHARS + 1)

    report = synthesize(
        storage, ScenarioLlm(synth_says(upsert_item("n-big", noticed=huge))), T0 + 2 * H, ok_vet, measure
    )

    assert report.outcome == "rejected"
    (run,) = runs(storage)
    assert run.rejected
    assert system_files(storage, "knowledge/changes/") == ["knowledge/changes/000001.json"]
    assert "n-big" not in memory_of(storage)
    assert knowledge.current(storage).rev == 1
