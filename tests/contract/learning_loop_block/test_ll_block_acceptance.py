"""Block tests of learning-loop (task 309): one per acceptance criterion (the feature closes with S6).

Slice tester, mode `block`; from `.engine/architecture/feature/learning-loop.md`, the slice contracts it names
and the public signatures, not the bodies. The live criteria (AC2's router set, AC3) are read from the
artifacts their slices name; the rest run on the local mode, the real Job and the real app.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml
from ll_fakes import (
    ARTIFACTS,
    CARDS,
    DAY,
    H_ALICE,
    H_OWNER,
    NOTES,
    OWNER,
    ROOT,
    SKIPPED,
    STEP,
    T0,
    Clock,
    H,
    M,
    Rec,
    ScenarioLlm,
    analyzer_says,
    local_environ,
    make_client,
    memory_of,
    ok_vet,
    outcome,
    page,
    say,
    seeded,
    snapshot,
    synth_says,
    system_files,
    system_json,
    topic_url,
    uk,
    upsert_item,
    with_chosen_step,
    zero_measure,
)

from thinkhow.facilitation.respond import system_instruction
from thinkhow.facilitation.route import router_instruction
from thinkhow.knowledge import Card, current, read_notes, rollback
from thinkhow.learning import job
from thinkhow.learning.analyze import analyze
from thinkhow.learning.observations import Observation
from thinkhow.learning.synthesize import synthesize
from thinkhow.learning.vet import measure, vet_with
from thinkhow.platform.storage import LocalStorage
from thinkhow.web.app import LiveKnowledge
from thinkhow.workspace import step_results_for_learning


def file_cards() -> dict[str, Card]:
    found = {}
    for path in sorted(CARDS.glob("*.yaml")):
        card = Card.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
        found[card.id] = card
    return found


def method_of(card: Card) -> list[tuple[str, str, list[str]]]:
    return [(p.id, p.goal, list(p.how)) for p in card.facilitator.phases]


def observe(storage: LocalStorage, at: Any) -> str:
    ref = with_chosen_step(storage, at)
    assert analyze(storage, ScenarioLlm(analyzer_says(anchor="t1")), at + H).written == 1
    return f"{ref.uid}/{ref.topic_id}/t1-t2/1"


# AC1. The method is not changed by learning: phases, goal and how of each of the 25 cards after a full
# cycle of learning are the same. Test.
def test_AC1_after_a_full_cycle_of_learning_phases_goal_and_how_of_all_25_cards_are_the_same(
    tmp_path: Path,
) -> None:
    root = tmp_path / "local"
    env = local_environ(root)
    assert job.run(["seed"], env, CARDS, lambda: T0) == 0
    storage = LocalStorage(root)
    card_files = snapshot(storage, "knowledge/cards/")
    assert job.run(["notes"], env, CARDS, lambda: T0 + M) == 0
    ref = with_chosen_step(storage, T0)
    say(storage, ref, "Вийшло: поговорив з трьома", T0 + DAY, recognize=Rec(outcome()))
    assert job.run(["analyze"], env, CARDS, lambda: T0 + DAY + H) == 0
    before = current(storage).rev
    assert job.run(["synthesize"], env, CARDS, lambda: T0 + DAY + 2 * H) == 0
    learned = current(storage).rev
    assert learned == before + 1
    rollback(storage, learned, OWNER.email, T0 + DAY + 3 * H)

    now = current(storage)
    expected = file_cards()
    assert len(expected) == 25
    assert sorted(now.cards) == sorted(expected)
    for cid, card in expected.items():
        assert method_of(now.cards[cid]) == method_of(card), cid
        assert now.cards[cid].facilitator.purpose == card.facilitator.purpose, cid
    assert snapshot(storage, "knowledge/cards/") == card_files


# AC1a: no path of learning (the synthesizer, the version check, the rollback) writes card files or changes
# the dict `cards` in a change record — an invariant by construction, not by care. Test.
def test_AC1a_synthesizer_vet_and_rollback_write_no_card_file_and_keep_the_cards_dict(tmp_path: Path) -> None:
    storage = seeded(tmp_path)
    seed_cards = system_json(storage, "knowledge/changes/000001.json")["cards"]
    vetted: list[str] = []

    def answer(schema: Any) -> dict[str, Any]:
        if "ok" in schema.model_fields:  # the vet's answer
            vetted.append("vet")
            return {"ok": True, "reason": ""}
        made: dict[str, Any] = synth_says(
            upsert_item("n-a", audience="router"), upsert_item("n-b", cards=["beta"])
        )(schema)
        return made

    llm = ScenarioLlm(answer)
    observe(storage, T0)
    del storage.writes[:]

    first = synthesize(storage, llm, T0 + 2 * H, vet_with(llm), measure)
    assert first.outcome == "applied" and vetted
    observe(storage, T0 + DAY)
    removing = ScenarioLlm(synth_says(remove=[{"id": "n-a", "observations": ["o1"]}]))
    second = synthesize(storage, removing, T0 + DAY + 2 * H, ok_vet, zero_measure)
    assert second.outcome == "applied"
    assert first.rev is not None and second.rev is not None
    rollback(storage, first.rev, OWNER.email, T0 + DAY + 3 * H)
    rollback(storage, second.rev, OWNER.email, T0 + DAY + 4 * H)

    learning_writes = [path for bucket, path in storage.writes if path.startswith("knowledge/")]
    assert learning_writes
    assert not [p for p in learning_writes if p.startswith("knowledge/cards/")]
    for path in system_files(storage, "knowledge/changes/"):
        assert system_json(storage, path)["cards"] == seed_cards, path


# AC2. Notes for all 25 methods lie in the experience memory (not in the cards) of the current revision,
# each with sources; the router set (scripts/router_eval.py, 85+ situations) with notes is not worse than
# the base: no case that was first in the base stops being first (unstable — repeat ×5, as PR-20).
def test_AC2_notes_of_all_25_methods_with_sources_and_the_router_set_with_notes_no_worse_than_the_base(
    tmp_path: Path,
) -> None:
    root = tmp_path / "local"
    env = local_environ(root)
    assert job.run(["seed"], env, CARDS, lambda: T0) == 0
    assert job.run(["notes"], env, CARDS, lambda: T0 + M) == 0
    now = current(LocalStorage(root))
    expected = file_cards()
    assert now.memory and {r.id for r in now.memory} == {r.id for r in read_notes(NOTES)}
    for cid in expected:
        mine = [r for r in now.memory if cid in r.cards]
        assert mine, cid
        assert all(r.basis.strip() for r in mine), cid
    for cid, card in expected.items():
        assert now.cards[cid] == card, cid  # the notes are not in the cards

    folder = ARTIFACTS / "starting-notes"
    runs = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(folder.glob("*.json"))]
    base = [r for r in runs if r["meta"]["rev"]["rev"] == 1]
    noted = [r for r in runs if r["meta"]["rev"]["rev"] > 1]
    assert base and noted
    base_run, notes_run = base[-1], noted[-1]
    assert base_run["meta"]["stamp"][:10] == notes_run["meta"]["stamp"][:10]  # the same day
    assert base_run["meta"]["cases_blob"] == notes_run["meta"]["cases_blob"]
    assert len(base_run["outcomes"]) >= 85
    assert {o["case_id"] for o in base_run["outcomes"]} == {o["case_id"] for o in notes_run["outcomes"]}
    with_notes = {o["case_id"]: o["first_ok"] for o in notes_run["outcomes"]}
    lost = [o["case_id"] for o in base_run["outcomes"] if o["first_ok"] and not with_notes[o["case_id"]]]

    def share(side: str, case: str) -> int:
        seen = []
        for path in sorted((folder / "repeats" / side).glob("*.json")):
            for o in json.loads(path.read_text(encoding="utf-8"))["outcomes"]:
                if o["case_id"] == case:
                    seen.append(o["first_ok"])
        assert len(seen) == 5, (side, case, seen)
        return sum(seen)

    for case in lost:
        assert share("notes", case) >= share("base", case), case


# AC3. The analyzer by the rules of analysis writes several observations a topic a night; on the
# conversation t-84d1517cb1c1 in the state «До» the observations «застрягла» are tied to #5, #11 and #15;
# the report has the observations of the old analyzer and of the new.
def test_AC3_the_live_report_ties_stuck_to_5_11_and_15_and_has_the_old_and_the_new_analyzer() -> None:
    report = (ARTIFACTS / "analysis-rules" / "owner-t-84d1517cb1c1.md").read_text(encoding="utf-8")
    last = report[report.rindex("## Спроба") :]
    raw = re.search(r"```json\n(.*?)\n```", last, re.S)
    assert raw is not None
    data = json.loads(raw.group(1))
    new = [Observation.model_validate(o) for o in data["new"]]
    assert len(new) >= 2  # several
    assert {o.turn for o in new if o.kind == "stuck"} >= {5, 11, 15}
    assert all(o.id.startswith("owner/t-84d1517cb1c1/") for o in new)
    assert data["old"], "the old analyzer's observations"
    assert "gemini-4-argon" in last and "eu" in last


# AC4. Steps and results: a person who returns to a topic with a chosen step sees the question «як вийшов
# крок?» and «чи стало ясніше?»; may not answer (P6); the question is not repeated and nowhere reminded
# (N4); the results are seen on the topic page (D1).
def test_AC4_the_question_on_return_may_be_skipped_is_not_repeated_and_results_are_on_the_topic_page(
    tmp_path: Path,
) -> None:
    storage = LocalStorage(tmp_path / "data")
    skipped = with_chosen_step(storage, T0)
    answered = with_chosen_step(storage, T0, step="Порахувати оренду")
    clock = Clock(T0 + H)
    rec = Rec(SKIPPED)
    client = make_client(tmp_path, storage, clock, recognize=rec)
    question = uk("step_question").replace("{step}", STEP)

    assert question not in page(client, topic_url(skipped), H_ALICE)  # not a return yet
    clock.now = T0 + DAY
    assert question in page(client, topic_url(skipped), H_ALICE)
    r = client.post(f"{topic_url(skipped)}/reply", data={"text": "Сьогодні про меню."}, headers=H_ALICE)
    assert r.status_code == 200
    _ = r.text
    assert rec.calls and rec.calls[0][0] == STEP
    clock.now = T0 + DAY + M
    shown = page(client, topic_url(skipped), H_ALICE)
    assert shown.count(question) == 1  # now a turn of ThinkHow in the conversation, no longer a pending line
    assert uk("steps_title") in shown and uk("step_no_answer") in shown
    clock.now = T0 + 3 * DAY  # the next return: not asked again
    assert page(client, topic_url(skipped), H_ALICE).count(question) == 1

    rec.result = outcome("worked", "partly", "оренда менша, ніж думав")
    client.post(f"{topic_url(answered)}/reply", data={"text": "Вийшло, оренда менша."}, headers=H_ALICE)
    clock.now = T0 + 3 * DAY + M
    shown = page(client, topic_url(answered), H_ALICE)
    for part in ("Порахувати оренду", uk("step_worked"), uk("clearer_partly"), "оренда менша, ніж думав"):
        assert part in shown, part
    (result,) = step_results_for_learning(storage, answered)
    assert (result.outcome, result.clearer) == ("worked", "partly")


# AC5. The synthesizer daily (the frequency is changed by one line of the schedule) from the observations
# and the results makes changes in the notes itself (and in the notes for the router) with versions; the
# owner sees the feed of changes with links to the places in conversations (G6) and can roll back any
# change.
def test_AC5_daily_synthesis_changes_router_and_facilitator_notes_the_feed_links_and_any_change_rolls_back(
    tmp_path: Path,
) -> None:
    deploy = (ROOT / "docs" / "deploy.md").read_text(encoding="utf-8")
    step = deploy[deploy.index("thinkhow-synthesize-daily") :]
    step = step[: step.index("```")]
    assert len(re.findall(r"--schedule=", step)) == 1
    assert "synthesize" in step.replace("thinkhow-synthesize-daily", "")

    storage = seeded(tmp_path)
    first_obs = observe(storage, T0)
    router_rev = synthesize(
        storage,
        ScenarioLlm(synth_says(upsert_item("n-r", audience="router", noticed="роутерне-слово"))),
        T0 + 2 * H,
        ok_vet,
        zero_measure,
    ).rev
    observe(storage, T0 + DAY)
    facil_rev = synthesize(
        storage,
        ScenarioLlm(synth_says(upsert_item("n-f", cards=["beta"], noticed="ведуче-слово"))),
        T0 + DAY + 2 * H,
        ok_vet,
        zero_measure,
    ).rev
    assert (router_rev, facil_rev) == (2, 3)
    assert sorted(memory_of(storage)) == ["n-f", "n-r"]
    assert system_files(storage, "knowledge/memory/n-r/") == ["knowledge/memory/n-r/v1.json"]

    client = make_client(tmp_path, storage, Clock(T0 + DAY + 3 * H))
    feed = page(client, "/learning", H_OWNER)
    uid, topic, _ = first_obs.split("/", 2)
    assert f"/topics/{uid}/{topic}#t1" in feed
    assert "/learning/rollback/2" in feed and "/learning/rollback/3" in feed
    assert client.post("/learning/rollback/2", headers=H_OWNER).status_code == 303  # not the newest one
    assert sorted(memory_of(storage)) == ["n-f"]


# AC6. The router and the facilitator read the notes of the current revision (F5 «зворотний шлях досвіду»).
def test_AC6_the_live_knowledge_of_the_service_gives_the_readers_the_notes_of_the_current_revision(
    tmp_path: Path,
) -> None:
    storage = seeded(tmp_path)
    live = LiveKnowledge(storage, current(storage))
    observe(storage, T0)
    rev = synthesize(
        storage,
        ScenarioLlm(
            synth_says(
                upsert_item("n-r", audience="router", noticed="живе-роутерне"),
                upsert_item("n-f", cards=["alpha"], noticed="живе-ведуче"),
            )
        ),
        T0 + 2 * H,
        ok_vet,
        zero_measure,
    ).rev
    assert rev is not None

    after = live.now()
    assert "живе-роутерне" in router_instruction(after, None)
    assert "живе-ведуче" in system_instruction(after.cards["alpha"], after.memory)

    rollback(storage, rev, OWNER.email, T0 + 3 * H)
    back = live.now()
    assert "живе-роутерне" not in router_instruction(back, None)
    assert "живе-ведуче" not in system_instruction(back.cards["alpha"], back.memory)


# AC7. One full cycle on test data: conversation → observations → step result → synthesizer → change in the
# feed → rollback — by one smoke script. Tests green.
def test_AC7_the_one_smoke_script_runs_the_whole_cycle_and_exits_0() -> None:
    kept = [ARTIFACTS / "synthesizer" / "smoke.txt", ARTIFACTS / "step-results" / "smoke.txt"]
    before = {p: p.read_bytes() if p.exists() else None for p in kept}
    try:
        done = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "smoke_test_learning_loop.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=300,
        )
    finally:
        for p, data in before.items():
            if data is None:
                p.unlink(missing_ok=True)
            else:
                p.write_bytes(data)
    assert done.returncode == 0, done.stdout[-2000:] + done.stderr[-2000:]
