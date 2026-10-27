"""Block tests of product-thinking-pack (task 307): one per line of «Inter-slice contracts», one per
acceptance criterion (the feature closes with S2 product-router-eval).

Slice tester, mode `block`; from `.engine/architecture/feature/product-thinking-pack.md`, the slice
contracts it names and the public signatures, not the bodies. Every test drives S1 (the 7 cards and their
cases) together with S2 (the measurement: `router_eval.py`, `router_eval_compare.py`, the live
conversations) or with the platform (the Knowledge, the Job `cards`, the service). Expected values are
written by hand from the artifact and the slice contracts.
"""

from __future__ import annotations

import json
import re
import shutil
from collections.abc import Iterator
from dataclasses import asdict
from pathlib import Path
from typing import Any

import yaml
from ptp_fakes import (
    ALICE,
    ARTIFACTS,
    BASE_RUN,
    CARDS,
    CASES,
    NEW_IDS,
    PREFIX,
    ROOT,
    S1_CLOSED,
    Model,
    Person,
    at,
    choose_raw,
    fac_raw,
    git,
    live_normalise,
    offer_raw,
    script,
    seeded_knowledge,
)

from thinkhow import knowledge, workspace
from thinkhow.learning import job
from thinkhow.platform.storage import LocalStorage, Storage
from thinkhow.web.app import build_deps

EVAL = ARTIFACTS / "router-eval"
REPEATS = EVAL / "repeats"
CONVERSATIONS = ARTIFACTS / "card-conversations"
CASES_PATH = "tests/fixtures/routing/cases.yaml"
# The commit where task 307 closed (S2 done): S2's window is S1_CLOSED..S2_CLOSED; later features
# (learning-loop, task 309) change the Knowledge code and the eval scripts on their own sealed contracts.
S2_CLOSED = "15134a2"


def drain(events: Iterator[Any]) -> list[Any]:
    return list(events)


def cases() -> list[dict[str, Any]]:
    return list(yaml.safe_load(CASES.read_text(encoding="utf-8"))["cases"])


def card_files() -> list[str]:
    return sorted(p.stem for p in CARDS.glob("*.yaml"))


def old_cards_dir(tmp: Path) -> Path:
    """The library before task 307: every card of `cards/` but the 7 new ones (18 cards)."""
    folder = tmp / "old-cards"
    folder.mkdir()
    for path in CARDS.glob("*.yaml"):
        if path.stem not in NEW_IDS:
            shutil.copy(path, folder / path.name)
    return folder


def local_environ(tmp: Path) -> dict[str, str]:
    return {
        "THINKHOW_LOCAL": "true",
        "THINKHOW_LOCAL_DIR": str(tmp),
        "THINKHOW_OWNER_EMAIL": "owner@localhost",
    }


def new_topic(store: Storage) -> workspace.TopicRef:
    workspace.ensure_profile(store, ALICE)
    workspace.set_language(store, ALICE, "uk-UA")
    return workspace.TopicRef(ALICE.id, workspace.create_topic(store, ALICE, "Тема", at(0)))


def routing_file(root: Path, ref: workspace.TopicRef) -> dict[str, Any]:
    path = root / "users" / ref.uid / ref.topic_id / "routing.json"
    loaded: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return loaded


def newest_run() -> Path:
    runs = sorted(EVAL.glob("*.json"))
    assert runs, EVAL
    return runs[-1]


def load_json(path: Path) -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return loaded


# ------------------------------------------------------------------ Inter-slice contracts


# S1 → S2: the ids of the 7 new cards and their cases; S2 edits only card texts — not ids, schema or cases;
# pre-mortem.yaml does not change
def test_s1_to_s2_the_seven_ids_and_their_cases_stand_as_s1_left_them_and_s2_edited_only_texts() -> None:
    for cid in NEW_IDS:
        path = CARDS / f"{cid}.yaml"
        assert path.is_file(), cid
        card = knowledge.Card.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
        assert card.id == cid
    positives = {c["expect"] for c in cases() if c["kind"] == "positive"}
    assert set(NEW_IDS) <= positives
    at_s1 = sorted(Path(p).stem for p in git("ls-tree", "--name-only", S1_CLOSED, "cards/").split())
    assert card_files() == at_s1
    assert git("diff", S1_CLOSED, "--", CASES_PATH) == ""
    assert git("diff", S1_CLOSED, S2_CLOSED, "--", "src/thinkhow/knowledge") == ""
    assert git("hash-object", str(CARDS / "pre-mortem.yaml")).strip().startswith("8f52b66a")


# S2 measures with the same scripts/router_eval.py (metrics of task 302: «перша» = candidates[0] or card_id
# on choose); its .json is what router_eval_compare reads
def test_s2_router_eval_outcomes_of_the_real_cases_are_what_compare_reads_case_by_case(
    tmp_path: Path,
) -> None:
    assert (
        git("diff", S1_CLOSED, S2_CLOSED, "--", "scripts/router_eval.py", "scripts/card_conversations.py")
        == ""
    )
    rev = script("router_eval")
    cmp_mod = script("router_eval_compare")
    _, k = seeded_knowledge(tmp_path)
    assert sorted(k.cards) == card_files()
    loaded = rev.load_cases(CASES)
    base = load_json(BASE_RUN)
    old_ids = {o["case_id"] for o in base["outcomes"]}
    by_text: dict[str, str] = {}
    for case in loaded:
        first = case.get("expect") or case["also_ok"][0]
        banned = {first, *case.get("also_ok", []), *case.get("absent", []), *case.get("not_first", [])}
        other = next(cid for cid in sorted(k.cards) if cid not in banned)
        if case["id"] == "co-1":  # an old case, first in the base: now another card first — a regression
            raw = offer_raw(other, first)
        elif case["id"] == "ci-neg-1":  # a hard negative of a new card: the forbidden card first
            raw = offer_raw("customer-interviews", "jobs-to-be-done")
        elif case["id"] not in old_ids and case["kind"] in ("positive", "tie"):
            raw = choose_raw(case["expect"])  # «перша» = card_id on choose
        else:
            raw = offer_raw(first, other)
        by_text[case["text"].strip()] = raw

    model = Model(router=lambda no, text: by_text[text.strip()])
    outcomes = rev.run(loaded, k, model, workers=2)
    assert len(outcomes) == len(loaded) == 119
    by_id = {o.case_id: o for o in outcomes}
    for case in loaded:
        if case["id"] not in old_ids and case["kind"] in ("positive", "tie"):
            o = by_id[case["id"]]
            assert (o.action, o.first, o.first_ok) == ("choose", case["expect"], True), o
    assert (by_id["co-1"].first_ok, by_id["ci-neg-1"].negative_ok) == (False, False)

    meta = dict(base["meta"])
    meta.update({"label": "block test", "stamp": "2026-10-25T000000Z", "cards": len(k.cards)})
    run = {
        "meta": meta,
        "summary": rev.summary(outcomes, sorted(k.cards)),
        "outcomes": [asdict(o) for o in outcomes],
        "llm_call": [],
    }
    run = json.loads(json.dumps(run, ensure_ascii=False))  # as written to and read from the .json
    cmp = cmp_mod.compare(run, base, old_ids, NEW_IDS)
    assert cmp["old"]["regressions"] == ["co-1"]
    assert sorted(cmp["old"]["fixed"]) == ["fw-2", "wr-1"]  # the two misses of the base
    assert cmp["old"]["missing"] == [] and cmp["old"]["unavailable"] == []
    assert cmp["new"]["negatives_broken"] == ["ci-neg-1"]
    assert cmp["new"]["unavailable"] == 0
    text = cmp_mod.render(cmp, meta)
    assert "Старі випадки" in text and "Нові випадки" in text
    assert "co-1" in text and "ci-neg-1" in text


# The edits of S2: no 6 words in a row of a case text get into a router item of a card (the sealed
# test_rev_cases.py boundary), and the cards still pass the F6 schema with their ids
def test_s2_card_texts_after_its_edits_share_no_six_words_in_a_row_with_a_case_text() -> None:
    normalise = live_normalise()

    def grams(text: str) -> set[tuple[str, ...]]:
        words = re.findall(r"[\w']+", normalise(text))
        return {tuple(words[i : i + 6]) for i in range(len(words) - 5)}

    of_cases: set[tuple[str, ...]] = set()
    for case in cases():
        of_cases |= grams(case["text"])
    assert of_cases
    for path in sorted(CARDS.glob("*.yaml")):
        card = knowledge.Card.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
        assert card.id == path.stem
        r = card.router
        for item in [r.needs, *r.when_yes, *r.when_no, *r.signals]:
            hit = grams(item) & of_cases
            assert not hit, (card.id, item, hit)


# ------------------------------------------------------------------ Acceptance criteria


# AC1: the new cards in cards/, the F6 schema takes them; the Job `cards` writes a new revision of the
# Knowledge with all the cards
def test_ac1_job_cards_publishes_the_25_cards_over_the_18_as_a_new_revision(tmp_path: Path) -> None:
    assert len(card_files()) == 25 and set(NEW_IDS) <= set(card_files())
    for cid in NEW_IDS:
        card = knowledge.Card.model_validate(
            yaml.safe_load((CARDS / f"{cid}.yaml").read_text(encoding="utf-8"))
        )
        assert isinstance(card.method, str) and card.method.strip(), cid
    environ = local_environ(tmp_path / "data")
    assert job.run(["seed"], environ, old_cards_dir(tmp_path), lambda: at(0)) == 0
    store = LocalStorage(tmp_path / "data")
    before = knowledge.current(store)
    assert len(before.cards) == 18 and not set(NEW_IDS) & set(before.cards)
    assert job.run(["cards"], environ, CARDS, lambda: at(1)) == 0
    after = knowledge.current(store)
    assert (after.rev, sorted(after.cards)) == (before.rev + 1, card_files())
    assert knowledge.publish(store, CARDS) is None


# AC2: the research — which methods and how many, with evidence and licences, why these and not others
def test_ac2_research_04_has_a_section_for_each_new_card_evidence_licences_and_what_was_left_out() -> None:
    text = (ROOT / "docs" / "research" / "04-product-pack.md").read_text(encoding="utf-8")
    headers = [line for line in text.splitlines() if line.startswith("#")]
    for cid in NEW_IDS:
        assert any(f"`{cid}`" in h for h in headers), cid
    assert "Tier" in text and "ліценз" in text.lower()
    assert any("не включено" in h for h in headers)
    assert any("Джерела" in h for h in headers) and text.count("http") >= 7


# AC3: at least 3 positives on each new card (the third — the held-out part) and 1 hard negative
def test_ac3_each_new_card_has_three_positives_the_third_held_out_and_a_hard_negative() -> None:
    all_cases = cases()
    by_id = {c["id"]: c for c in all_cases}
    for cid, prefix in PREFIX.items():
        for n in (1, 2, 3):
            case = by_id.get(f"{prefix}-{n}")
            assert case is not None and (case["kind"], case["expect"]) == ("positive", cid), (cid, n)
        negatives = [c for c in all_cases if c["kind"] == "negative" and cid in c.get("not_first", [])]
        assert negatives, cid


# AC3: a run through the real model on all the cases; the old and the new cases apart; old against the base
def test_ac3_run_is_the_real_model_on_the_frozen_set_and_its_compare_md_is_compare_against_the_base() -> None:
    path = newest_run()
    run = load_json(path)
    assert run["meta"]["model"] == "gemini-4-argon" and run["meta"]["cards"] == 25
    assert run["meta"]["cases_blob"] == git("rev-parse", f"{S1_CLOSED}:{CASES_PATH}").strip()
    assert sorted(o["case_id"] for o in run["outcomes"]) == sorted(c["id"] for c in cases())
    base = load_json(BASE_RUN)
    old_ids = {o["case_id"] for o in base["outcomes"]}
    assert len(old_ids) == 85
    cmp = script("router_eval_compare").compare(run, base, old_ids, NEW_IDS)
    compare_md = path.with_name(path.stem + ".compare.md")
    assert compare_md.is_file(), compare_md.name
    text = compare_md.read_text(encoding="utf-8")
    assert "Старі випадки" in text and "Нові випадки" in text
    assert BASE_RUN.stem in text
    for cid in [*cmp["old"]["regressions"], *cmp["old"]["fixed"], *NEW_IDS]:
        assert f"`{cid}`" in text, cid


# AC3 («Не гірше»): wr-1, fw-2 and every old case changed between the base and the run — ×5 on 18 and on 25
def test_ac3_every_changed_old_case_and_the_unstable_ones_are_repeated_five_times_on_each_side() -> None:
    run = load_json(newest_run())
    base = load_json(BASE_RUN)
    old_ids = {o["case_id"] for o in base["outcomes"]}
    cmp = script("router_eval_compare").compare(run, base, old_ids, NEW_IDS)
    due = {"wr-1", "fw-2", *cmp["old"]["regressions"], *cmp["old"]["fixed"]}
    summary = (REPEATS / "summary.md").read_text(encoding="utf-8")
    rows = [line for line in summary.splitlines() if line.startswith("|")]
    for side in ("18", "25"):
        runs = [load_json(p) for p in sorted((REPEATS / side).glob("*.json"))]
        for cid in sorted(due):
            holding = [r for r in runs if any(o["case_id"] == cid for o in r["outcomes"])]
            assert len(holding) >= 5, (side, cid, len(holding))
    for cid in sorted(due):
        assert any(f"`{cid}`" in row for row in rows), cid


# AC4: one live conversation on every new card, to its end (`end: done`)
def test_ac4_every_new_card_leads_a_conversation_to_its_end_and_has_its_live_report(tmp_path: Path) -> None:
    cc = script("card_conversations")
    _, k = seeded_knowledge(tmp_path)
    by_id = {c["id"]: c for c in cases()}
    for cid, prefix in PREFIX.items():
        ids = [p.id for p in k.cards[cid].facilitator.phases]
        led: list[int] = []

        def router(no: int, text: str, cid: str = cid) -> str:
            return choose_raw(cid) if text.startswith("Давай") else offer_raw(cid, "jobs-to-be-done")

        def facilitator(no: int, text: str, ids: list[str] = ids, led: list[int] = led) -> str:
            led.append(no)
            i = min(len(led), len(ids)) - 1
            return fac_raw(ids[i], exit_met=i == len(ids) - 1)

        model = Model(router=router, facilitator=facilitator)
        conv = cc.converse_card(k, model, Person(), cid, by_id[f"{prefix}-1"]["text"])
        assert (conv.target, conv.led, conv.offered, conv.done, conv.seeded) == (cid, cid, True, True, False)
        assert conv.phases == ids
        for call in model.stream_calls:
            assert knowledge.card_prompt(k.cards[cid]) in call.system
    folders = [d for d in sorted(CONVERSATIONS.iterdir()) if (d / "index.md").is_file()]
    for cid in NEW_IDS:
        holding = [d for d in folders if (d / f"{cid}.md").is_file()]
        assert holding, f"no live conversation of {cid}"
        assert f"({cid}.md)" in (holding[-1] / "index.md").read_text(encoding="utf-8"), cid


# AC5: what the router offers now on the first reply of the conversation t-84d1517cb1c1
def test_ac5_the_newest_router_smoke_on_t_84d1517cb1c1_offers_two_or_three_of_the_cards() -> None:
    smokes = sorted((ARTIFACTS / "spikes").glob("product-cards-router-live-*.txt"))
    assert smokes, "no smoke of the router on t-84d1517cb1c1"
    text = smokes[-1].read_text(encoding="utf-8")
    assert "t-84d1517cb1c1" in text and "результат: PASS" in text
    assert "дія: offer" in text
    answer = text.split("## Відповідь 1", 1)[1].split("\n## ", 1)[0]
    offered = re.findall(r"^- ([a-z0-9-]+):", answer, re.M)
    assert 2 <= len(offered) <= 3, offered
    assert set(offered) <= set(card_files()), offered


# AC6 (closing step): the Job `cards`, then the restarted service reads the new revision with the 25 cards
def test_ac6_job_cards_then_a_restarted_service_carries_the_25_cards_and_routes_with_the_new_revision(
    tmp_path: Path,
) -> None:
    environ = local_environ(tmp_path / "data")
    assert job.run(["seed"], environ, old_cards_dir(tmp_path), lambda: at(0)) == 0
    before = build_deps(environ, CARDS)
    assert job.run(["cards"], environ, CARDS, lambda: at(1)) == 0
    after = build_deps(environ, CARDS)
    for deps, rev, ids in ((before, 1, 18), (after, 2, 25)):
        bound: Any = deps.facilitate
        assert bound.keywords["knowledge"].rev == rev
        assert len(bound.keywords["knowledge"].cards) == ids
        ref = new_topic(deps.storage)
        drain(workspace.reply(deps.storage, deps.facilitate, ALICE, ref, "Як мені це продати?", at(2)))
        decisions = routing_file(tmp_path / "data", ref)["decisions"]
        assert [d["rev"]["rev"] for d in decisions] == [rev]
    assert set(NEW_IDS) <= set(after.facilitate.keywords["knowledge"].cards)  # type: ignore[attr-defined]
