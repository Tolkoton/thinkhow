"""Contract tests of skel-workspace: sessions, silence and the legacy closed marker, Seam 3 (slice tester)."""

from datetime import timedelta
from pathlib import Path

import pytest
from skelw_fakes import (
    ALICE,
    H24,
    S1,
    T0,
    LlmUnavailable,
    ScenarioFacilitate,
    conv_bytes,
    conv_lines,
    conv_path,
    drain,
    ok,
)

from thinkhow.facilitation.types import Turn
from thinkhow.platform.storage import LocalStorage
from thinkhow.workspace import (
    Answered,
    Delta,
    Failed,
    NothingToRetry,
    NumberedTurn,
    Saved,
    Session,
    TopicRef,
    create_topic,
    open_topic,
    reply,
    retry,
    topic_sessions,
)

ASK = "Хочу відкрити кав'ярню."
ANS = "Що може піти не так?"


def topic(store: LocalStorage) -> TopicRef:
    return TopicRef("alice-1", create_topic(store, ALICE, "Тема", T0))


def append_legacy_closed(store: LocalStorage, ref: TopicRef, line: str) -> None:
    """Append a `closed` marker as the earlier versions' (removed) button wrote it."""
    text = conv_bytes(store, ref).decode("utf-8").rstrip("\n")
    store.write("users", conv_path(ref), f"{text}\n\n{line}\n".encode(), "text/markdown; charset=utf-8")


def test_reply_one_second_before_silence_stays_in_the_session(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    ref = topic(store)
    fac = ScenarioFacilitate(store, [ok(ANS), ok("Друге?")])
    drain(reply(store, fac, ALICE, ref, ASK, T0))
    late = T0 + H24 - S1
    assert [s.closed_at for s in topic_sessions(store, ref, late)] == [None]
    assert open_topic(store, ALICE, ref, late).sessions[0].closed_at is None
    assert drain(reply(store, fac, ALICE, ref, "ще", late))[0] == Saved(3)
    view = open_topic(store, ALICE, ref, late)
    assert len(view.sessions) == 1 and [t.no for t in view.sessions[0].turns] == [1, 2, 3, 4]
    assert fac.calls[1].context.history == [Turn("user", ASK), Turn("model", ANS)]


def test_reply_at_silence_opens_session_2_and_closes_session_1(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    ref = topic(store)
    fac = ScenarioFacilitate(store, [ok(ANS), ok("Нова сесія?"), ok("Третя?")])
    drain(reply(store, fac, ALICE, ref, ASK, T0))
    s1_turns = [NumberedTurn(1, "user", ASK, T0), NumberedTurn(2, "model", ANS, T0)]
    assert topic_sessions(store, ref, T0 + H24 - S1) == [Session(1, s1_turns, None)]
    assert topic_sessions(store, ref, T0 + H24) == [Session(1, s1_turns, T0 + H24)]
    at = T0 + H24
    assert drain(reply(store, fac, ALICE, ref, "повернувся", at)) == [
        Saved(3),
        Delta("Що "),
        Delta("може?"),
        Answered(4),
    ]
    assert "<!-- thinkhow:session 2 -->" in conv_lines(store, ref)
    assert fac.calls[1].context.history == [] and fac.calls[1].context.turn_no == 3
    drain(reply(store, fac, ALICE, ref, "далі", at + timedelta(hours=1)))
    assert fac.calls[2].context.history == [Turn("user", "повернувся"), Turn("model", "Нова сесія?")]
    view = open_topic(store, ALICE, ref, at + timedelta(hours=1))
    assert [s.no for s in view.sessions] == [1, 2]
    assert view.sessions[0].turns == s1_turns and view.sessions[0].closed_at == T0 + H24
    assert [t.no for t in view.sessions[1].turns] == [3, 4, 5, 6] and view.sessions[1].closed_at is None


def test_silence_counts_from_the_recorded_second(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    ref = topic(store)
    fac = ScenarioFacilitate(store, [ok(ANS), ok("Знову?")])
    drain(reply(store, fac, ALICE, ref, ASK, T0 + timedelta(microseconds=900_000)))
    view = open_topic(store, ALICE, ref, T0 + H24 + timedelta(microseconds=500_000))
    assert view.sessions[0].turns[0].at == T0
    assert view.sessions[0].closed_at == T0 + H24
    assert drain(reply(store, fac, ALICE, ref, "ще", T0 + H24 + timedelta(microseconds=500_000)))[0] == Saved(
        3
    )
    assert len(open_topic(store, ALICE, ref, T0 + H24 + S1).sessions) == 2


def test_unanswered_turn_stays_in_a_silence_closed_session(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    ref = topic(store)
    fac = ScenarioFacilitate(store, [[LlmUnavailable("down")], ok(ANS)])
    assert drain(reply(store, fac, ALICE, ref, ASK, T0)) == [Saved(1), Failed("LlmUnavailable")]
    assert open_topic(store, ALICE, ref, T0 + H24 - S1).awaiting_answer is True
    assert open_topic(store, ALICE, ref, T0 + H24).awaiting_answer is False
    with pytest.raises(NothingToRetry):
        retry(store, fac, ALICE, ref, T0 + H24)
    assert drain(reply(store, fac, ALICE, ref, "знову", T0 + H24))[0] == Saved(2)
    view = open_topic(store, ALICE, ref, T0 + H24)
    assert view.sessions[0].turns == [NumberedTurn(1, "user", ASK, T0)]
    assert view.sessions[0].closed_at == T0 + H24
    assert [(t.no, t.role) for t in view.sessions[1].turns] == [(2, "user"), (3, "model")]
    assert topic_sessions(store, ref, T0 + H24) == [
        Session(1, [NumberedTurn(1, "user", ASK, T0)], T0 + H24),
        Session(
            2,
            [NumberedTurn(2, "user", "знову", T0 + H24), NumberedTurn(3, "model", ANS, T0 + H24)],
            None,
        ),
    ]


def test_unanswered_turn_stays_in_a_legacy_marker_closed_session(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    ref = topic(store)
    fac = ScenarioFacilitate(store, [[LlmUnavailable("down")], ok(ANS)])
    drain(reply(store, fac, ALICE, ref, ASK, T0))
    append_legacy_closed(store, ref, "<!-- thinkhow:closed 1 2026-10-22T17:00:00Z -->")  # T0 + 1h
    view = open_topic(store, ALICE, ref, T0 + timedelta(hours=1))
    assert view.awaiting_answer is False and view.sessions[0].closed_at == T0 + timedelta(hours=1)
    with pytest.raises(NothingToRetry):
        retry(store, fac, ALICE, ref, T0 + timedelta(hours=1))
    assert drain(reply(store, fac, ALICE, ref, "знову", T0 + timedelta(hours=2)))[0] == Saved(2)
    view2 = open_topic(store, ALICE, ref, T0 + timedelta(hours=2))
    assert view2.sessions[0].turns == [NumberedTurn(1, "user", ASK, T0)]
    assert [t.no for t in view2.sessions[1].turns] == [2, 3]


def test_a_legacy_closed_marker_stays_once_and_keeps_its_time(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    ref = topic(store)
    fac = ScenarioFacilitate(store, [ok(ANS), ok("Друге?")])
    drain(reply(store, fac, ALICE, ref, ASK, T0))
    marker = "<!-- thinkhow:closed 1 2026-10-22T16:05:00Z -->"  # T0 + 5 min
    append_legacy_closed(store, ref, marker)
    drain(reply(store, fac, ALICE, ref, "ще", T0 + timedelta(minutes=9)))
    lines = conv_lines(store, ref)
    assert lines.count(marker) == 1
    assert lines.index(marker) < lines.index("<!-- thinkhow:session 2 -->")
    assert len([line for line in lines if line.startswith("<!-- thinkhow:closed")]) == 1
    view = open_topic(store, ALICE, ref, T0 + timedelta(minutes=9))
    assert view.sessions[0].closed_at == T0 + timedelta(minutes=5)
    assert [t.no for t in view.sessions[1].turns] == [3, 4] and view.sessions[1].closed_at is None


def test_silence_closes_a_session_without_writing_a_closed_marker(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    ref = topic(store)
    fac = ScenarioFacilitate(store, [ok(ANS), ok("Знову?")])
    drain(reply(store, fac, ALICE, ref, ASK, T0))
    before = conv_bytes(store, ref)
    view = open_topic(store, ALICE, ref, T0 + timedelta(hours=30))
    assert len(view.sessions) == 1 and view.sessions[0].closed_at == T0 + H24
    assert conv_bytes(store, ref) == before
    drain(reply(store, fac, ALICE, ref, "ще", T0 + timedelta(hours=30)))
    assert not [line for line in conv_lines(store, ref) if line.startswith("<!-- thinkhow:closed")]


def test_session_without_turns_is_not_closed_by_silence(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    ref = topic(store)
    later = T0 + timedelta(hours=72)
    assert open_topic(store, ALICE, ref, later).sessions[0].closed_at is None
    assert drain(reply(store, ScenarioFacilitate(store, [ok(ANS)]), ALICE, ref, ASK, later))[0] == Saved(1)
    view = open_topic(store, ALICE, ref, later)
    assert len(view.sessions) == 1 and [t.no for t in view.sessions[0].turns] == [1, 2]


def test_empty_session_closed_by_a_legacy_marker_stays_closed_and_empty(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    ref = topic(store)
    append_legacy_closed(store, ref, "<!-- thinkhow:closed 1 2026-10-22T16:01:00Z -->")  # T0 + 1 min
    assert open_topic(store, ALICE, ref, T0 + timedelta(minutes=1)).sessions[0].closed_at == T0 + timedelta(
        minutes=1
    )
    assert topic_sessions(store, ref, T0 + timedelta(days=5)) == [Session(1, [], T0 + timedelta(minutes=1))]
    drain(reply(store, ScenarioFacilitate(store, [ok(ANS)]), ALICE, ref, ASK, T0 + timedelta(minutes=2)))
    view = open_topic(store, ALICE, ref, T0 + timedelta(minutes=2))
    assert [s.no for s in view.sessions] == [1, 2]
    assert view.sessions[0].turns == [] and [t.no for t in view.sessions[1].turns] == [1, 2]


def test_topic_sessions_gives_every_session_with_its_turns(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    ref = topic(store)
    fac = ScenarioFacilitate(store, [ok(ANS), ok("Б?"), ok("В?")])
    drain(reply(store, fac, ALICE, ref, ASK, T0))
    append_legacy_closed(store, ref, "<!-- thinkhow:closed 1 2026-10-22T16:10:00Z -->")  # T0 + 10 min
    t2 = T0 + timedelta(hours=1)
    drain(reply(store, fac, ALICE, ref, "друга", t2))
    t3 = t2 + H24
    drain(reply(store, fac, ALICE, ref, "третя", t3))
    assert topic_sessions(store, ref, t3) == [
        Session(
            1,
            [NumberedTurn(1, "user", ASK, T0), NumberedTurn(2, "model", ANS, T0)],
            T0 + timedelta(minutes=10),
        ),
        Session(2, [NumberedTurn(3, "user", "друга", t2), NumberedTurn(4, "model", "Б?", t2)], t2 + H24),
        Session(3, [NumberedTurn(5, "user", "третя", t3), NumberedTurn(6, "model", "В?", t3)], None),
    ]
