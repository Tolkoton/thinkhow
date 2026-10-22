"""Contract tests of skel-workspace: reply and retry, Seam 2 (slice tester; from the contract)."""

from datetime import datetime
from pathlib import Path

import pytest
from skelw_fakes import (
    ALICE,
    BOB,
    T0,
    LlmUnavailable,
    ScenarioFacilitate,
    SpyStorage,
    conv_bytes,
    conv_path,
    drain,
    map_path,
    ok,
    update,
)

from thinkhow.facilitation.types import (
    FacilitationContext,
    FacilitationError,
    MapItem,
    ProblemMap,
    Turn,
)
from thinkhow.platform.storage import LocalStorage
from thinkhow.workspace import (
    Answered,
    Delta,
    Failed,
    NothingToRetry,
    NumberedTurn,
    PendingAnswer,
    Saved,
    TopicNotFound,
    TopicRef,
    close_session,
    create_topic,
    open_topic,
    reply,
    retry,
)

ASK = "Хочу відкрити кав'ярню."
ANS = "Що може піти не так?"


def topic(store: LocalStorage) -> TopicRef:
    return TopicRef("alice-1", create_topic(store, ALICE, "Тема", T0))


def test_happy_reply_events_turns_context_and_map(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    ref = topic(store)
    add = {"op": "add", "id": "i1", "type": "plan", "text": "кав'ярня", "turn": "t1"}
    fac = ScenarioFacilitate(store, [ok(ANS, deltas=["Що ", "може?"], phase="p1", updates=[add])])
    events = drain(reply(store, fac, ALICE, ref, ASK, T0))
    assert events == [Saved(1), Delta("Що "), Delta("може?"), Answered(2)]
    assert fac.calls[0].context == FacilitationContext(
        card_id="pre-mortem", history=[], problem_map=ProblemMap(), turn_no=1, text=ASK
    )
    view = open_topic(store, ALICE, ref, T0)
    assert view.sessions[0].turns == [
        NumberedTurn(1, "user", ASK, T0),
        NumberedTurn(2, "model", ANS, T0),
    ]
    assert view.awaiting_answer is False
    expected_map = ProblemMap(
        items=[MapItem(id="i1", type="plan", text="кав'ярня", turn="t1")], phase_id="p1", last_turn=2
    )
    assert view.problem_map == expected_map
    raw = store.read("users", map_path(ref))
    assert raw is not None and ProblemMap.model_validate_json(raw) == expected_map


def test_second_reply_gets_session_history_current_map_and_next_number(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    ref = topic(store)
    add = {"op": "add", "id": "i1", "type": "plan", "text": "кав'ярня", "turn": "t1"}
    fac = ScenarioFacilitate(store, [ok(ANS, phase="p1", updates=[add]), ok("Друге питання?", phase="p2")])
    drain(reply(store, fac, ALICE, ref, ASK, T0))
    events = drain(reply(store, fac, ALICE, ref, "Друга репліка", T0))
    assert events[0] == Saved(3) and events[-1] == Answered(4)
    ctx = fac.calls[1].context
    assert ctx.history == [Turn("user", ASK), Turn("model", ANS)]
    assert ctx.problem_map == ProblemMap(
        items=[MapItem(id="i1", type="plan", text="кав'ярня", turn="t1")], phase_id="p1", last_turn=2
    )
    assert ctx.turn_no == 3 and ctx.card_id == "pre-mortem"
    assert open_topic(store, ALICE, ref, T0).problem_map.last_turn == 4


def test_write_order_human_turn_first_then_answer_then_map(tmp_path: Path) -> None:
    store = SpyStorage(tmp_path)
    ref = topic(store)
    store.writes.clear()
    fac = ScenarioFacilitate(store, [ok(ANS)])
    it = reply(store, fac, ALICE, ref, ASK, T0)
    first = next(it)
    assert first == Saved(1)
    assert ASK in conv_bytes(store, ref).decode()
    rest = list(it)
    assert rest[-1] == Answered(2)
    at_call = fac.calls[0].files_at_call[conv_path(ref)].decode()
    assert ASK in at_call and ANS not in at_call
    paths = [w.path for w in store.writes]
    answer_write = next(
        i for i, w in enumerate(store.writes) if w.path == conv_path(ref) and ANS in w.data.decode()
    )
    assert paths.count(map_path(ref)) == 1
    assert answer_write < paths.index(map_path(ref))
    for w in store.writes:
        assert w.bucket == "users"
        if w.path == conv_path(ref):
            assert w.content_type == "text/markdown; charset=utf-8"
        if w.path == map_path(ref):
            assert w.content_type == "application/json"


def test_failure_midway_keeps_human_turn_then_retry_answers(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    ref = topic(store)
    map_before = store.read("users", map_path(ref))
    fac = ScenarioFacilitate(
        store,
        [["Що ", "мо", LlmUnavailable("down")], ok(ANS, deltas=["Що?"], updates=[])],
    )
    events = drain(reply(store, fac, ALICE, ref, ASK, T0))
    assert events == [Saved(1), Delta("Що "), Delta("мо"), Failed("LlmUnavailable")]
    view = open_topic(store, ALICE, ref, T0)
    assert view.sessions[0].turns == [NumberedTurn(1, "user", ASK, T0)]
    assert view.awaiting_answer is True
    assert store.read("users", map_path(ref)) == map_before
    events2 = drain(retry(store, fac, ALICE, ref, T0))
    assert events2 == [Delta("Що?"), Answered(2)]
    assert fac.calls[1].context == FacilitationContext(
        card_id="pre-mortem", history=[], problem_map=ProblemMap(), turn_no=1, text=ASK
    )
    view2 = open_topic(store, ALICE, ref, T0)
    assert [(t.no, t.role, t.text) for t in view2.sessions[0].turns] == [(1, "user", ASK), (2, "model", ANS)]
    assert view2.awaiting_answer is False


def test_stream_without_update_is_failed_no_update(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    ref = topic(store)
    map_before = store.read("users", map_path(ref))
    events = drain(reply(store, ScenarioFacilitate(store, [["Що ", "далі?"]]), ALICE, ref, ASK, T0))
    assert events == [Saved(1), Delta("Що "), Delta("далі?"), Failed("NoUpdate")]
    assert store.read("users", map_path(ref)) == map_before
    view = open_topic(store, ALICE, ref, T0)
    assert [t.no for t in view.sessions[0].turns] == [1] and view.awaiting_answer is True


def test_any_exception_class_name_is_the_failed_reason(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    ref = topic(store)
    fac = ScenarioFacilitate(
        store, [[FacilitationError("bad update")], ["x", KeyError("k")], [ValueError("v")], ok(ANS)]
    )
    assert drain(reply(store, fac, ALICE, ref, ASK, T0)) == [Saved(1), Failed("FacilitationError")]
    assert drain(retry(store, fac, ALICE, ref, T0)) == [Delta("x"), Failed("KeyError")]
    assert drain(retry(store, fac, ALICE, ref, T0)) == [Failed("ValueError")]
    assert drain(retry(store, fac, ALICE, ref, T0)) == [Delta("Що "), Delta("може?"), Answered(2)]


def test_answer_text_is_normalized_and_empty_answer_fails(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    ref = topic(store)
    map_before = store.read("users", map_path(ref))
    fac = ScenarioFacilitate(store, [[update("   ")], [update("\r\n \r")], [update("  ok\r\n")]])
    assert drain(reply(store, fac, ALICE, ref, ASK, T0)) == [Saved(1), Failed("EmptyReply")]
    assert store.read("users", map_path(ref)) == map_before
    view = open_topic(store, ALICE, ref, T0)
    assert [t.no for t in view.sessions[0].turns] == [1] and view.awaiting_answer is True
    assert drain(retry(store, fac, ALICE, ref, T0)) == [Failed("EmptyReply")]
    assert drain(retry(store, fac, ALICE, ref, T0)) == [Answered(2)]
    assert open_topic(store, ALICE, ref, T0).sessions[0].turns[1].text == "ok"


def test_human_text_is_normalized_before_saving(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    ref = topic(store)
    fac = ScenarioFacilitate(store, [ok(ANS)])
    drain(reply(store, fac, ALICE, ref, "  перший\r\nдругий\rтретій \r\n", T0))
    assert open_topic(store, ALICE, ref, T0).sessions[0].turns[0].text == "перший\nдругий\nтретій"


def test_first_update_ends_the_stream(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    ref = topic(store)
    fac = ScenarioFacilitate(store, [["Що?", update(ANS), "зайве", RuntimeError("never read")]])
    assert drain(reply(store, fac, ALICE, ref, ASK, T0)) == [Saved(1), Delta("Що?"), Answered(2)]
    assert fac.read_after_update is False
    assert open_topic(store, ALICE, ref, T0).sessions[0].turns[1].text == ANS


def test_map_updates_apply_in_order(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    ref = topic(store)
    first = [
        {"op": "add", "id": "i1", "type": "plan", "text": "план", "turn": "t1"},
        {"op": "add", "id": "i2", "type": "goal", "text": "мета", "turn": "t1"},
        {"op": "add", "id": "i3", "type": "threat", "text": "загроза", "turn": "t1"},
    ]
    second = [
        {"op": "update", "id": "i2", "type": "assumption", "text": "припущення", "turn": "t3"},
        {"op": "add", "id": "i1", "type": "plan", "text": "план 2", "turn": "t3"},
        {"op": "remove", "id": "i3", "type": "threat", "text": "загроза", "turn": "t3"},
        {"op": "update", "id": "zz", "type": "goal", "text": "нема", "turn": "t3"},
        {"op": "remove", "id": "yy", "type": "goal", "text": "нема", "turn": "t3"},
        {"op": "add", "id": "i4", "type": "mitigation", "text": "захист", "turn": "t3"},
    ]
    fac = ScenarioFacilitate(store, [ok(ANS, phase="p1", updates=first), ok(ANS, phase="p2", updates=second)])
    drain(reply(store, fac, ALICE, ref, ASK, T0))
    drain(reply(store, fac, ALICE, ref, "ще", T0))
    assert open_topic(store, ALICE, ref, T0).problem_map == ProblemMap(
        items=[
            MapItem(id="i1", type="plan", text="план 2", turn="t3"),
            MapItem(id="i2", type="assumption", text="припущення", turn="t3"),
            MapItem(id="i4", type="mitigation", text="захист", turn="t3"),
        ],
        phase_id="p2",
        last_turn=4,
    )


def test_foreign_reply_raises_at_call_without_iteration(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    ref = topic(store)
    before = conv_bytes(store, ref)
    fac = ScenarioFacilitate(store, [ok(ANS)])
    with pytest.raises(TopicNotFound):
        reply(store, fac, BOB, ref, ASK, T0)
    assert fac.calls == [] and conv_bytes(store, ref) == before


def test_pre_stream_errors_raise_at_call(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    ref = topic(store)
    fac = ScenarioFacilitate(store, [[LlmUnavailable("down")], ok(ANS)])
    for empty in ["", "   ", " \r\n\r "]:
        with pytest.raises(ValueError):
            reply(store, fac, ALICE, ref, empty, T0)
    with pytest.raises(NothingToRetry):
        retry(store, fac, ALICE, ref, T0)
    drain(reply(store, fac, ALICE, ref, ASK, T0))
    with pytest.raises(PendingAnswer):
        reply(store, fac, ALICE, ref, "друга поспіль", T0)
    assert drain(retry(store, fac, ALICE, ref, T0))[-1] == Answered(2)
    with pytest.raises(NothingToRetry):
        retry(store, fac, ALICE, ref, T0)
    assert len(fac.calls) == 2


def test_naive_now_in_writing_functions_is_value_error(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    ref = topic(store)
    naive = datetime(2026, 10, 22, 16, 0, 0)
    fac = ScenarioFacilitate(store, [[LlmUnavailable("down")]])
    with pytest.raises(ValueError):
        drain(reply(store, fac, ALICE, ref, ASK, naive))
    drain(reply(store, fac, ALICE, ref, ASK, T0))
    with pytest.raises(ValueError):
        drain(retry(store, fac, ALICE, ref, naive))
    with pytest.raises(ValueError):
        close_session(store, ALICE, ref, naive)
