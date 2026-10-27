"""Contract tests of analysis-rules (learning-loop S2): the analyzer's input, schema, file and card_id.

Slice tester; from the contract `.engine/slices/analysis-rules.md`, not the code.
"""

import json
from pathlib import Path
from typing import Any

import pytest
from ar_fakes import (
    ALICE,
    BOB,
    CTX,
    DAY,
    NEW,
    NOW,
    H,
    M,
    SetLlm,
    SpyStorage,
    d_choose,
    d_end,
    d_offer,
    item_schema,
    new_topic,
    obs,
    obs_names,
    observations_prop,
    one,
    say,
    seed_cards,
    talk,
)
from pydantic import BaseModel, ValidationError

from thinkhow import workspace
from thinkhow.learning.analyze import ANALYZER, AnalyzeReport, analyze, answer_schema
from thinkhow.learning.local import local_script
from thinkhow.platform.llm import LlmUnavailable, Turn
from thinkhow.platform.storage import LocalStorage


def _card_ids(storage: LocalStorage, ref: workspace.TopicRef, name: str) -> list[Any]:
    return [o["card_id"] for o in obs(storage, ref, name)["observations"]]


def _turns(storage: LocalStorage, ref: workspace.TopicRef, name: str) -> list[int]:
    return [o["turn"] for o in obs(storage, ref, name)["observations"]]


# --- Seam 1: card_id on the edges ------------------------------------------------------------------


def test_seam1_card_id_on_the_edges_of_choose_and_end(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path / "b")
    seed_cards(storage, tmp_path)
    ref = new_topic(storage, ALICE, NOW - 2 * H)
    plan = {1: [d_offer(1, "alpha", "beta")], 3: [d_choose(3, "beta")], 9: [d_end(9, "beta", "not_fit")]}
    talk(storage, ALICE, ref, 6, NOW - H, plan)  # turns 1..12
    anchors = ["t3", "t4", "t5", "t9", "t10", "t11", "t2"]
    llm = SetLlm(plan=lambda _: [one(a) for a in anchors])
    assert analyze(storage, llm, NOW) == AnalyzeReport(written=1, skipped=0, failed=0)
    assert obs_names(storage, ref) == {"t1-t12.json"}
    assert _turns(storage, ref, "t1-t12.json") == [3, 4, 5, 9, 10, 11, 2]
    assert _card_ids(storage, ref, "t1-t12.json") == [None, "beta", "beta", "beta", "beta", None, None]


def test_seam1_card_id_is_none_without_routing_json_and_after_an_offer_without_choose(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path / "b")
    seed_cards(storage, tmp_path)
    bare = new_topic(storage, ALICE, NOW - 2 * H)
    talk(storage, ALICE, bare, 2, NOW - H)
    offered = new_topic(storage, BOB, NOW - 2 * H)
    talk(storage, BOB, offered, 2, NOW - H, {1: [d_offer(1, "alpha", "beta")]})
    llm = SetLlm(plan=lambda anchors: [one(a) for a in anchors])
    assert analyze(storage, llm, NOW) == AnalyzeReport(written=2, skipped=0, failed=0)
    assert _card_ids(storage, bare, "t1-t4.json") == [None, None, None, None]
    assert _card_ids(storage, offered, "t1-t4.json") == [None, None, None, None]


def test_card_id_takes_no_model_call_one_call_per_topic(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path / "b")
    seed_cards(storage, tmp_path)
    a = new_topic(storage, ALICE, NOW - 2 * H)
    talk(storage, ALICE, a, 3, NOW - H, {1: [d_choose(1, "alpha")]})
    b = new_topic(storage, BOB, NOW - 2 * H)
    talk(storage, BOB, b, 3, NOW - H, {1: [d_offer(1, "alpha", "beta")], 3: [d_choose(3, "beta")]})
    llm = SetLlm(plan=lambda anchors: [one(a) for a in anchors])
    assert analyze(storage, llm, NOW) == AnalyzeReport(written=2, skipped=0, failed=0)
    assert len(llm.calls) == 2
    assert _card_ids(storage, a, "t1-t6.json") == [None, "alpha", "alpha", "alpha", "alpha", "alpha"]
    assert _card_ids(storage, b, "t1-t6.json") == [None, None, None, "beta", "beta", "beta"]


# --- Seam 2: the model's input ---------------------------------------------------------------------


def test_seam2_status_lines_stand_before_the_turn_the_decision_acts_from_in_context_and_new(
    tmp_path: Path,
) -> None:
    storage = LocalStorage(tmp_path / "b")
    seed_cards(storage, tmp_path)
    t0 = NOW - 3 * H
    ref = new_topic(storage, ALICE, t0 - M)
    plan = {1: [d_offer(1, "alpha", "beta")], 3: [d_choose(3, "alpha")]}
    talk(storage, ALICE, ref, 2, t0, plan)  # turns 1..4
    analyze(storage, SetLlm(), t0 + 10 * M)
    talk(storage, ALICE, ref, 2, t0 + 20 * M, {5: [d_end(5, "alpha", "done")]}, first_no=5)  # turns 5..8

    other = new_topic(storage, BOB, t0 - M)
    talk(storage, BOB, other, 3, t0, {1: [d_choose(1, "beta")], 3: [d_end(3, "beta", "not_fit")]})

    llm = SetLlm()
    assert analyze(storage, llm, NOW) == AnalyzeReport(written=2, skipped=0, failed=0)
    by_first = {c.lines()[0]: c for c in llm.calls}
    assert by_first[CTX].lines() == [
        CTX,
        "#1 людина: людина 1",
        "[Роутер: запропоновано alpha, beta]",
        "#2 фасилітатор: фасилітатор 2",
        "#3 людина: людина 3",
        "[Метод: Альфа (alpha)]",
        "#4 фасилітатор: фасилітатор 4",
        NEW,
        "#5 людина: людина 5",
        "#6 фасилітатор: фасилітатор 6",
        "[Метод закінчено: alpha — пройдено]",
        "#7 людина: людина 7",
        "#8 фасилітатор: фасилітатор 8",
    ]
    assert by_first["#1 людина: людина 1"].lines() == [
        "#1 людина: людина 1",
        "[Метод: Бета (beta)]",
        "#2 фасилітатор: фасилітатор 2",
        "#3 людина: людина 3",
        "#4 фасилітатор: фасилітатор 4",
        "[Метод закінчено: beta — не підходить]",
        "#5 людина: людина 5",
        "#6 фасилітатор: фасилітатор 6",
    ]


def test_seam2_without_routing_json_there_is_no_status_line(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path / "b")
    seed_cards(storage, tmp_path)
    ref = new_topic(storage, ALICE, NOW - 2 * H)
    talk(storage, ALICE, ref, 2, NOW - H)
    llm = SetLlm()
    analyze(storage, llm, NOW)
    assert len(llm.calls) == 1
    assert llm.calls[0].lines() == [
        "#1 людина: людина 1",
        "#2 фасилітатор: фасилітатор 2",
        "#3 людина: людина 3",
        "#4 фасилітатор: фасилітатор 4",
    ]
    assert obs_names(storage, ref) == {"t1-t4.json"}


def test_a_status_line_that_falls_outside_the_shown_turns_is_not_written(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path / "b")
    seed_cards(storage, tmp_path)
    t0 = NOW - 3 * DAY
    ref = new_topic(storage, ALICE, t0 - M)
    say(storage, ALICE, ref, "людина 1", "фасилітатор 2", t0, [d_offer(1, "alpha", "beta")])
    analyze(storage, SetLlm(), t0 + H)
    # a new session (more than 24 h of silence): no context; the offer's line (before #2) is not shown;
    # the end on 3 acts from #5, which does not exist yet
    later = t0 + DAY + H
    say(
        storage,
        ALICE,
        ref,
        "людина 3",
        "фасилітатор 4",
        later,
        [d_choose(3, "beta"), d_end(3, "beta", "done")],
    )
    llm = SetLlm()
    assert analyze(storage, llm, later + H) == AnalyzeReport(written=1, skipped=0, failed=0)
    assert llm.calls[0].lines() == [
        "#3 людина: людина 3",
        "[Метод: Бета (beta)]",
        "#4 фасилітатор: фасилітатор 4",
    ]


def test_a_card_missing_from_knowledge_or_no_knowledge_gives_the_id_only_and_the_topic_does_not_fail(
    tmp_path: Path,
) -> None:
    for name, seeded in (("missing-card", True), ("no-knowledge", False)):
        storage = LocalStorage(tmp_path / name)
        if seeded:
            seed_cards(storage, tmp_path / name, {"alpha": "Альфа"})
        ref = new_topic(storage, ALICE, NOW - 2 * H)
        talk(storage, ALICE, ref, 1, NOW - H, {1: [d_choose(1, "zeta")]})
        llm = SetLlm(plan=lambda anchors: [one(a) for a in anchors])
        assert analyze(storage, llm, NOW) == AnalyzeReport(written=1, skipped=0, failed=0), name
        lines = llm.calls[0].lines()
        assert lines[0] == "#1 людина: людина 1", name
        assert lines[-1] == "#2 фасилітатор: фасилітатор 2", name
        assert len(lines) == 3, name
        assert lines[1].startswith("[Метод:") and "zeta" in lines[1], name
        assert _card_ids(storage, ref, "t1-t2.json") == [None, "zeta"], name


# --- the answer schema -----------------------------------------------------------------------------


def test_answer_schema_has_the_fields_in_order_and_the_enums(tmp_path: Path) -> None:
    schema = answer_schema([3, 4, 5])
    top = schema.model_json_schema()
    assert list(top["properties"]) == ["observations"]
    item = item_schema(schema)
    assert list(item["properties"]) == ["kind", "finding", "worked", "cause", "anchor"]
    props = item["properties"]

    def enum(name: str) -> list[str]:
        p = props[name]
        if "$ref" in p:
            p = top["$defs"][p["$ref"].rsplit("/", 1)[-1]]
        return list(p["enum"])

    assert sorted(enum("kind")) == ["method_fit", "progress", "stuck"]
    assert sorted(enum("cause")) == ["circumstances", "facilitation", "method", "router"]
    assert enum("anchor") == ["t3", "t4", "t5"]
    assert props["finding"]["minLength"] == 1
    assert enum_of_single_turn() == ["t7"]


def enum_of_single_turn() -> list[str]:
    item = item_schema(answer_schema([7]))
    return list(item["properties"]["anchor"]["enum"])


def test_answer_schema_needs_at_least_one_observation_and_has_no_upper_bound(tmp_path: Path) -> None:
    schema: type[BaseModel] = answer_schema([1, 2])
    assert observations_prop(schema).get("minItems") == 1
    assert "maxItems" not in observations_prop(schema)
    with pytest.raises(ValidationError):
        schema.model_validate({"observations": []})
    many = [one("t1"), one("t2")] * 6
    got = schema.model_validate({"observations": many})
    assert len(got.model_dump()["observations"]) == 12
    for bad in (
        {**one("t1"), "anchor": "t3"},
        {**one("t1"), "kind": "step"},
        {**one("t1"), "cause": "luck"},
        {**one("t1"), "finding": ""},
    ):
        with pytest.raises(ValidationError):
            schema.model_validate({"observations": [bad]})


# --- the file --------------------------------------------------------------------------------------


def test_the_file_is_a_set_with_ids_links_card_ids_and_the_sets_analyzed_at(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path / "b")
    seed_cards(storage, tmp_path)
    t0 = NOW - 3 * H
    ref = new_topic(storage, ALICE, t0 - M)
    talk(storage, ALICE, ref, 1, t0, {1: [d_choose(1, "alpha")]})
    analyze(storage, SetLlm(), t0 + 10 * M)
    talk(storage, ALICE, ref, 2, t0 + 20 * M, first_no=3)  # turns 3..6
    answer = [
        {
            "kind": "method_fit",
            "finding": "метод не підійшов",
            "worked": False,
            "cause": "method",
            "anchor": "t5",
        },
        {"kind": "progress", "finding": "нове розуміння", "worked": True, "cause": "router", "anchor": "t3"},
    ]
    assert analyze(storage, SetLlm(plan=lambda _: answer), NOW) == AnalyzeReport(
        written=1, skipped=0, failed=0
    )
    assert obs_names(storage, ref) == {"t1-t2.json", "t3-t6.json"}
    got = obs(storage, ref, "t3-t6.json")
    assert set(got) == {"uid", "topic_id", "first_turn", "last_turn", "analyzed_at", "observations"}
    assert (got["uid"], got["topic_id"], got["first_turn"], got["last_turn"]) == (
        ALICE.id,
        ref.topic_id,
        3,
        6,
    )
    base = f"{ALICE.id}/{ref.topic_id}/t3-t6"
    link = f"/topics/{ALICE.id}/{ref.topic_id}"
    expected = [
        {
            "id": f"{base}/1",
            "turn": 5,
            "link": f"{link}#t5",
            "kind": "method_fit",
            "worked": False,
            "finding": "метод не підійшов",
            "cause": "method",
            "card_id": "alpha",
        },
        {
            "id": f"{base}/2",
            "turn": 3,
            "link": f"{link}#t3",
            "kind": "progress",
            "worked": True,
            "finding": "нове розуміння",
            "cause": "router",
            "card_id": "alpha",
        },
    ]
    for o in got["observations"]:
        assert o["analyzed_at"] == got["analyzed_at"]
    assert [{k: v for k, v in o.items() if k != "analyzed_at"} for o in got["observations"]] == expected


def test_a_model_failure_counts_failed_and_writes_nothing(tmp_path: Path) -> None:
    class Strict(BaseModel):
        x: int

    try:
        Strict.model_validate({})
    except ValidationError as exc:
        invalid = exc
    for name, err in (("down", LlmUnavailable("down")), ("invalid", invalid)):
        storage = LocalStorage(tmp_path / name)
        ref = new_topic(storage, ALICE, NOW - 2 * H)
        talk(storage, ALICE, ref, 1, NOW - H)
        assert analyze(storage, SetLlm(fail_all=err), NOW) == AnalyzeReport(written=0, skipped=0, failed=1)
        assert obs_names(storage, ref) == set(), name


def test_the_analyzer_writes_only_under_system_learning_observations(tmp_path: Path) -> None:
    storage = SpyStorage(tmp_path / "b")
    seed_cards(storage, tmp_path)
    ref = new_topic(storage, ALICE, NOW - 2 * H)
    talk(storage, ALICE, ref, 2, NOW - H, {1: [d_offer(1, "alpha", "beta")], 3: [d_choose(3, "alpha")]})
    storage.recording = True
    assert analyze(storage, SetLlm(), NOW) == AnalyzeReport(written=1, skipped=0, failed=0)
    assert storage.writes, "the analyzer wrote nothing"
    for w in storage.writes:
        assert w.bucket == "system" and w.path.startswith("learning/observations/"), w


# --- local mode ------------------------------------------------------------------------------------


def test_local_script_answers_one_progress_observation_anchored_to_the_first_of_the_enum() -> None:
    schema = answer_schema([3, 4])
    raw = local_script(ANALYZER, [Turn(role="user", text="#3 людина: план")], schema)
    got = schema.model_validate(json.loads(raw)).model_dump()
    assert list(got) == ["observations"]
    assert len(got["observations"]) == 1
    assert got["observations"][0]["kind"] == "progress"
    assert got["observations"][0]["anchor"] == "t3"


# --- workspace.topic_routing -----------------------------------------------------------------------


def test_topic_routing_reads_the_decisions_in_order_and_none_without_routing_json(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path / "b")
    bare = new_topic(storage, ALICE, NOW - 2 * H)
    talk(storage, ALICE, bare, 1, NOW - H)
    routed = new_topic(storage, BOB, NOW - 2 * H)
    decisions = [d_offer(1, "alpha", "beta"), d_choose(3, "beta"), d_end(3, "beta", "not_fit")]
    talk(storage, BOB, routed, 2, NOW - H, {1: decisions[:1], 3: decisions[1:]})
    assert workspace.topic_routing(storage, bare) == ()
    assert workspace.topic_routing(storage, routed) == tuple(decisions)
    assert {r.topic_id for r in workspace.all_topics_for_learning(storage)} == {
        bare.topic_id,
        routed.topic_id,
    }
