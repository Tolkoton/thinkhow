"""Contract tests of skel-workspace: profile, topics, listing, opening (slice tester; from the contract)."""

import json
import re
from datetime import datetime
from pathlib import Path

import pytest
from skelw_fakes import ALICE, BOB, OWNER, T0, SpyStorage, conv_lines, map_path

from thinkhow.access import CurrentUser
from thinkhow.facilitation.types import ProblemMap
from thinkhow.platform.storage import LocalStorage
from thinkhow.workspace import (
    Session,
    TopicNotFound,
    TopicRef,
    TopicSummary,
    TopicView,
    all_topics_for_learning,
    closed_sessions,
    create_topic,
    ensure_profile,
    list_topics,
    open_topic,
)


def test_ensure_profile_creates_profile_json_with_email_once(tmp_path: Path) -> None:
    store = SpyStorage(tmp_path)
    ensure_profile(store, ALICE)
    raw = store.read("users", "alice-1/profile.json")
    assert raw is not None
    assert json.loads(raw) == {"email": "alice@example.com"}
    assert [(w.op, w.path) for w in store.writes] == [("create_if_absent", "alice-1/profile.json")]
    store.write(
        "users", "alice-1/profile.json", b'{"email": "alice@example.com", "kept": 1}', "application/json"
    )
    ensure_profile(store, ALICE)
    assert store.read("users", "alice-1/profile.json") == b'{"email": "alice@example.com", "kept": 1}'


def test_create_topic_id_shape_and_files(tmp_path: Path) -> None:
    store = SpyStorage(tmp_path)
    tid = create_topic(store, ALICE, "Відкрити кав'ярню", T0)
    assert re.fullmatch(r"t-[0-9a-f]{12}", tid)
    ref = TopicRef(uid="alice-1", topic_id=tid)
    assert [line for line in conv_lines(store, ref) if line != ""] == [
        "<!-- thinkhow:format 1 -->",
        "# Відкрити кав'ярню",
        "<!-- thinkhow:session 1 -->",
    ]
    raw_map = store.read("users", map_path(ref))
    assert raw_map is not None
    assert ProblemMap.model_validate_json(raw_map) == ProblemMap()
    kinds = {w.path: w.content_type for w in store.writes}
    assert kinds[f"alice-1/{tid}/conversation.md"] == "text/markdown; charset=utf-8"
    assert kinds[f"alice-1/{tid}/map.json"] == "application/json"
    assert {w.bucket for w in store.writes} == {"users"}
    assert create_topic(store, ALICE, "Друга", T0) != tid


def test_open_new_topic_view(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    tid = create_topic(store, ALICE, "Тема", T0)
    ref = TopicRef("alice-1", tid)
    assert open_topic(store, ALICE, ref, T0) == TopicView(
        ref=ref,
        title="Тема",
        sessions=[Session(no=1, turns=[], closed_at=None)],
        problem_map=ProblemMap(),
        awaiting_answer=False,
    )


def test_title_is_one_line_trimmed_and_round_trips(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    cases = {
        "  Перший\nрядок  ": "Перший рядок",
        "<!-- thinkhow:session 2 -->": "<!-- thinkhow:session 2 -->",
        "\\назва": "\\назва",
        "😀 план": "😀 план",
    }
    for raw, expected in cases.items():
        tid = create_topic(store, ALICE, raw, T0)
        view = open_topic(store, ALICE, TopicRef("alice-1", tid), T0)
        assert view.title == expected
        assert len(view.sessions) == 1


def test_empty_title_is_value_error(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    for raw in ["", "   ", "\n \n"]:
        with pytest.raises(ValueError):
            create_topic(store, ALICE, raw, T0)
    assert store.list("users", "") == []


def test_list_topics_own_only_in_topic_id_order(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    mine = {create_topic(store, ALICE, f"Тема {i}", T0): f"Тема {i}" for i in range(4)}
    create_topic(store, BOB, "Чужа", T0)
    create_topic(store, OWNER, "Власника", T0)
    expected = [TopicSummary(TopicRef("alice-1", t), mine[t]) for t in sorted(mine)]
    assert list_topics(store, ALICE) == expected
    owner_list = list_topics(store, OWNER)
    assert [s.title for s in owner_list] == ["Власника"]
    assert list_topics(store, CurrentUser(id="nobody", email="n@example.com", is_owner=False)) == []


def test_all_topics_for_learning_from_conversation_paths(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    assert list(all_topics_for_learning(store)) == []
    a = create_topic(store, ALICE, "A", T0)
    b = create_topic(store, BOB, "B", T0)
    ensure_profile(store, ALICE)
    store.write("users", "bob_2/t-0123456789ab/map.json", b"{}", "application/json")
    store.write("users", "bob_2/t-XYZ/conversation.md", b"x", "text/markdown; charset=utf-8")
    store.write("users", "bob_2/t-0123456789abc/conversation.md", b"x", "text/markdown; charset=utf-8")
    store.write("users", "bad.uid/t-0123456789ab/conversation.md", b"x", "text/markdown; charset=utf-8")
    got = list(all_topics_for_learning(store))
    assert sorted(got, key=lambda r: (r.uid, r.topic_id)) == [TopicRef("alice-1", a), TopicRef("bob_2", b)]


def test_open_topic_without_map_json_gives_empty_map(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    tid = create_topic(store, ALICE, "Тема", T0)
    (tmp_path / "users" / "alice-1" / tid / "map.json").unlink()
    assert open_topic(store, ALICE, TopicRef("alice-1", tid), T0).problem_map == ProblemMap()


def test_naive_now_is_value_error(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    naive = datetime(2026, 10, 22, 16, 0, 0)
    with pytest.raises(ValueError):
        create_topic(store, ALICE, "Тема", naive)
    tid = create_topic(store, ALICE, "Тема", T0)
    ref = TopicRef("alice-1", tid)
    with pytest.raises(ValueError):
        open_topic(store, ALICE, ref, naive)
    with pytest.raises(ValueError):
        closed_sessions(store, ref, naive)


def test_closed_sessions_unknown_or_malformed_ref_is_topic_not_found(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    create_topic(store, ALICE, "Тема", T0)
    for ref in [
        TopicRef("alice-1", "t-000000000000"),
        TopicRef("alice-1", "../x"),
        TopicRef("..", "t-000000000000"),
        TopicRef("alice-1", "t-ABCDEF012345"),
    ]:
        with pytest.raises(TopicNotFound):
            closed_sessions(store, ref, T0)
