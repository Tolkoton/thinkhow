"""Invariants I1-I4 of analysis-rules on the topic the live script builds (catch-up of
`scripts/analyze_owner_conversation.py`). Slice tester: from the contract and the script's public names.

The topic is the one the script puts into its temporary folder (`before_turns()` → `topic_folder(...)`: the 18
turns of «До», routing offer on 1 and choose `opportunity-tree` on 3); the new analyzer runs on it with
planned model answers chosen by hand from each invariant's Domain.
"""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from aoc_fakes import PlanLlm, load_script

from thinkhow.learning.analyze import analyze
from thinkhow.learning.observations import read_all
from thinkhow.platform.storage import LocalStorage

START = datetime(2026, 10, 25, 12, 0, 0, tzinfo=UTC)
NOW = datetime(2026, 10, 27, 3, 0, 0, tzinfo=UTC)
PREFIX = "learning/observations/"


def owner_topic(tmp_path: Path) -> LocalStorage:
    module = load_script()
    storage = LocalStorage(tmp_path / "data")
    module.topic_folder(storage, module.before_turns(), START)
    return storage


def analyzed(
    tmp_path: Path, plan: list[tuple[int, str, str, bool]]
) -> tuple[LocalStorage, list[dict[str, Any]]]:
    storage = owner_topic(tmp_path)
    analyze(storage, PlanLlm(plan=plan), NOW)
    files = []
    for path in sorted(storage.list("system", PREFIX)):
        raw = storage.read("system", path)
        assert raw is not None
        files.append(json.loads(raw))
    assert files, "the analyzer wrote an observation file"
    return storage, files


def test_I1_every_anchor_is_a_new_turn_of_the_owner_topic(tmp_path: Path) -> None:
    # both edges (t1, t18), a repeat (t5 twice), the turn after the choice (t4)
    plan = [
        (1, "progress", "router", True),
        (18, "method_fit", "method", False),
        (5, "stuck", "facilitation", False),
        (5, "method_fit", "method", False),
        (4, "progress", "facilitation", True),
    ]
    _, files = analyzed(tmp_path, plan)
    assert len(files) == 1
    data = files[0]
    assert (data["first_turn"], data["last_turn"]) == (1, 18)
    turns = []
    for o in data["observations"]:
        assert data["first_turn"] <= o["turn"] <= data["last_turn"]
        assert o["link"].endswith(f"#t{o['turn']}")
        turns.append(o["turn"])
    assert turns == [1, 18, 5, 5, 4]


def test_I2_read_all_ids_unique_and_stable_on_the_owner_topic(tmp_path: Path) -> None:
    plan = [
        (15, "stuck", "method", False),
        (15, "method_fit", "method", False),
        (5, "stuck", "facilitation", False),
    ]
    storage, _ = analyzed(tmp_path, plan)
    first = [o.id for o in read_all(storage)]
    second = [o.id for o in read_all(storage)]
    assert first == second
    assert len(set(first)) == len(first)
    assert first == [
        "owner/t-84d1517cb1c1/t1-t18/1",
        "owner/t-84d1517cb1c1/t1-t18/2",
        "owner/t-84d1517cb1c1/t1-t18/3",
    ]


def test_I3_the_whole_answer_is_kept_in_its_order(tmp_path: Path) -> None:
    # seven, not sorted by anchor, a repeat
    plan = [
        (15, "stuck", "method", False),
        (5, "stuck", "facilitation", False),
        (17, "stuck", "circumstances", False),
        (13, "progress", "facilitation", True),
        (5, "method_fit", "router", False),
        (9, "progress", "method", True),
        (11, "stuck", "method", False),
    ]
    _, files = analyzed(tmp_path, plan)
    observations = files[0]["observations"]
    assert [(o["turn"], o["kind"], o["cause"]) for o in observations] == [
        (15, "stuck", "method"),
        (5, "stuck", "facilitation"),
        (17, "stuck", "circumstances"),
        (13, "progress", "facilitation"),
        (5, "method_fit", "router"),
        (9, "progress", "method"),
        (11, "stuck", "method"),
    ]
    assert [o["id"].rsplit("/", 1)[-1] for o in observations] == ["1", "2", "3", "4", "5", "6", "7"]


def test_I4_card_id_follows_the_rebuilt_routing_on_every_anchor(tmp_path: Path) -> None:
    # every new turn as an anchor: offer on 1 → None; choose on 3 → None on 3 itself, the card from 4 on
    plan = [(n, "progress", "facilitation", True) for n in range(1, 19)]
    _, files = analyzed(tmp_path, plan)
    got = {o["turn"]: o["card_id"] for o in files[0]["observations"]}
    expected = {1: None, 2: None, 3: None} | {n: "opportunity-tree" for n in range(4, 19)}
    assert got == expected
