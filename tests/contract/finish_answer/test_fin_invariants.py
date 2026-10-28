"""Contract tests of finish-answer: one test per invariant I1-I5 (slice tester, from the contract only)."""

from __future__ import annotations

import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from fin_fakes import (
    ALICE,
    T0,
    WAIT,
    ArmedStorage,
    Boom,
    Down,
    Fac,
    Step,
    asgi_call,
    log_lines,
    make_app,
    make_pending,
    new_store,
    seed_topic,
    snapshot,
    sse_events,
    turns,
    update,
)

from thinkhow.platform import log
from thinkhow.web.server import _sse, _stream
from thinkhow.workspace import (
    Answered,
    Delta,
    Failed,
    NothingToRetry,
    ReplyEvent,
    Saved,
    TopicRef,
    delete_topic,
    open_topic,
    reply,
    retry,
    set_language,
)

ASK = "Хочу відкрити кав'ярню."
ANSWER = "Що може піти не так, друга частина"
FIRST, REST = "Що може піти не так", ", друга частина"


def url(ref: TopicRef, tail: str) -> str:
    return f"/topics/{ref.uid}/{ref.topic_id}{tail}"


def latched_script(answer_first: str = FIRST, answer_rest: str = REST) -> list[Step]:
    # Seam 1: the answer ends only after the disconnect was delivered (the latch); then a delta, the update
    return [answer_first, WAIT, answer_rest, update(answer_first + answer_rest)]


def tracked(
    items: list[ReplyEvent], end_with: BaseException | None = None
) -> tuple[Iterator[ReplyEvent], list[str]]:
    """An iterator of reply events with a pause between them; `done` gets "end" once it is read to its end."""
    done: list[str] = []

    def gen() -> Iterator[ReplyEvent]:
        for item in items:
            time.sleep(0.05)
            yield item
        time.sleep(0.2)
        done.append("end")
        if end_with is not None:
            raise end_with

    return gen(), done


# --- I1 ------------------------------------------------------------------------------------------


def test_I1_events_are_read_to_the_end_when_the_asgi_call_returns_whatever_the_client_does(
    tmp_path: Path,
) -> None:
    # (a) reply, the client goes before the first event: the answer is under turn_no + 1 at return
    store = new_store(tmp_path / "a")
    fac = Fac([latched_script()])
    app = make_app(tmp_path / "a", store, fac)
    ref = seed_topic(store, "Тема")
    asgi_call(app, url(ref, "/reply"), "disconnect_at_once", {"text": ASK}, fac.latch)
    assert turns(store, ref) == [(1, "user", ASK), (2, "model", ANSWER)]
    with pytest.raises(NothingToRetry):
        retry(store, Fac(), ALICE, ref, T0)

    # (b) reply on a topic with an exchange, the client goes after the first delta
    store = new_store(tmp_path / "b")
    fac = Fac([latched_script()])
    app = make_app(tmp_path / "b", store, fac)
    ref = seed_topic(store, "Тема", [("Перше питання", "Перша відповідь")])
    call = asgi_call(app, url(ref, "/reply"), "disconnect_after_delta", {"text": ASK}, fac.latch)
    assert b"event: delta" in call.body  # the disconnect really came after the first delta
    assert turns(store, ref) == [
        (1, "user", "Перше питання"),
        (2, "model", "Перша відповідь"),
        (3, "user", ASK),
        (4, "model", ANSWER),
    ]
    with pytest.raises(NothingToRetry):
        retry(store, Fac(), ALICE, ref, T0)

    # (c) retry, the client goes after the first delta
    store = new_store(tmp_path / "c")
    fac = Fac([latched_script()])
    app = make_app(tmp_path / "c", store, fac)
    ref = seed_topic(store, "Тема")
    make_pending(store, ref, ASK)
    asgi_call(app, url(ref, "/retry"), "disconnect_after_delta", {}, fac.latch)
    assert turns(store, ref) == [(1, "user", ASK), (2, "model", ANSWER)]
    with pytest.raises(NothingToRetry):
        retry(store, Fac(), ALICE, ref, T0)

    # (d) the response of `_stream` itself: iterators that end with `answered`, `failed` or an exception
    endings: list[tuple[list[ReplyEvent], BaseException | None]] = [
        ([Saved(1), Delta("а"), Delta("б"), Answered(2)], None),
        ([Saved(1), Delta("а"), Failed("ModelDown")], None),
        ([Saved(1), Delta("а"), Delta("б")], Boom("mid-stream")),
    ]
    for items, end_with in endings:
        for mode in ("disconnect_at_once", "disconnect_after_delta", "read_all"):
            events, done = tracked(items, end_with)
            asgi_call(_stream(events), "/x", mode)
            assert done == ["end"], (items, end_with, mode)


# --- I2 ------------------------------------------------------------------------------------------


def test_I2_a_client_that_reads_to_the_end_gets_the_events_of_sse_over_the_same_iterator(
    tmp_path: Path,
) -> None:
    cases: list[tuple[list[ReplyEvent], BaseException | None, list[tuple[str, object]]]] = [
        ([], None, []),
        (
            [Saved(1), Delta("Перший рядок,\n"), Delta("другий — «так» 🌍"), Answered(2)],
            None,
            [
                ("saved", {"turn": 1}),
                ("delta", {"text": "Перший рядок,\n"}),
                ("delta", {"text": "другий — «так» 🌍"}),
                ("answered", {"turn": 2}),
            ],
        ),
        (
            [Delta("а"), Failed("ModelDown")],
            None,
            [("delta", {"text": "а"}), ("failed", {"reason": "ModelDown"})],
        ),
        (
            [Saved(3), Delta("а")],
            Boom("mid-stream"),
            [("saved", {"turn": 3}), ("delta", {"text": "а"}), ("failed", {"reason": "Internal"})],
        ),
    ]
    for items, end_with, expected in cases:
        events, _ = tracked(items, end_with)
        body = asgi_call(_stream(events), "/x", "read_all").body.decode()
        reference, _ = tracked(items, end_with)
        assert body == "".join(_sse(reference)), items
        assert sse_events(body) == expected, items

    # through the route, on the scripted facilitator
    store = new_store(tmp_path)
    fac = Fac([["Так", ", звісно", update("Так, звісно")]])
    app = make_app(tmp_path, store, fac)
    ref = seed_topic(store, "Тема")
    body = asgi_call(app, url(ref, "/reply"), "read_all", {"text": ASK}).body.decode()
    assert sse_events(body) == [
        ("saved", {"turn": 1}),
        ("delta", {"text": "Так"}),
        ("delta", {"text": ", звісно"}),
        ("answered", {"turn": 2}),
    ]


# --- I3 ------------------------------------------------------------------------------------------


def test_I3_log_lines_written_while_the_events_are_read_carry_the_request_id(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    def probe() -> None:
        log.log_event("fa_probe")

    # a facilitator line, the client reads to the end
    store = new_store(tmp_path / "a")
    fac = Fac([["Так", probe, update("Так")]])
    app = make_app(tmp_path / "a", store, fac)
    ref = seed_topic(store, "Тема")
    capsys.readouterr()
    asgi_call(
        app,
        url(ref, "/reply"),
        "read_all",
        {"text": ASK},
        extra_headers=[(b"x-cloud-trace-context", b"trace-a/1;o=1")],
    )
    probes = [line for line in log_lines(capsys.readouterr().out) if line.get("event") == "fa_probe"]
    assert [line["request_id"] for line in probes] == ["trace-a"]

    # a facilitator line after the client went
    store = new_store(tmp_path / "b")
    fac = Fac([["Так", WAIT, probe, ", так", update("Так, так")]])
    app = make_app(tmp_path / "b", store, fac)
    ref = seed_topic(store, "Тема")
    capsys.readouterr()
    asgi_call(
        app,
        url(ref, "/reply"),
        "disconnect_after_delta",
        {"text": ASK},
        fac.latch,
        extra_headers=[(b"x-cloud-trace-context", b"trace-b/1;o=1")],
    )
    probes = [line for line in log_lines(capsys.readouterr().out) if line.get("event") == "fa_probe"]
    assert [line["request_id"] for line in probes] == ["trace-b"]

    # the error line of a storage failure after the client went (stream_error or reply_failed)
    root = tmp_path / "c"
    armed = ArmedStorage(root / "data")
    set_language(armed, ALICE, "uk-UA")

    def arm() -> None:
        armed.armed = True

    fac = Fac([["Так", WAIT, ", так", arm, update("Так, так")]])
    app = make_app(root, armed, fac)
    ref = seed_topic(armed, "Тема")
    capsys.readouterr()
    asgi_call(
        app,
        url(ref, "/reply"),
        "disconnect_after_delta",
        {"text": ASK},
        fac.latch,
        extra_headers=[(b"x-cloud-trace-context", b"trace-c/1;o=1")],
    )
    errors = [
        line
        for line in log_lines(capsys.readouterr().out)
        if line.get("event") in ("stream_error", "reply_failed")
    ]
    assert errors, "no error line from the reading after the client went"
    assert {line["request_id"] for line in errors} == {"trace-c"}


# --- I4 ------------------------------------------------------------------------------------------


def _step_to_first_delta(events: Iterator[ReplyEvent]) -> list[ReplyEvent]:
    seen: list[ReplyEvent] = []
    for event in events:
        seen.append(event)
        if isinstance(event, Delta):
            return seen
    raise AssertionError(f"no delta before the end: {seen}")


def test_I4_a_late_answer_changes_no_file_when_the_last_turn_is_not_its_unanswered_turn(
    tmp_path: Path,
) -> None:
    # (1) a retry B answers turn 1 and the person writes C with its answer while A waits
    store = new_store(tmp_path / "1")
    ref = seed_topic(store, "Тема")
    a = reply(store, Fac([["А-1", "А-2", update("А-1А-2", [ADD])]]), ALICE, ref, ASK, T0)
    _step_to_first_delta(a)
    list(retry(store, Fac([["Б", update("Б")]]), ALICE, ref, T0))
    list(reply(store, Fac([["В-відповідь", update("В-відповідь")]]), ALICE, ref, "В", T0))
    before = snapshot(store)
    list(a)
    assert snapshot(store) == before

    # (2) B answers turn 1, the person writes C and its answer fails: the last turn is the person's, no 3
    store = new_store(tmp_path / "2")
    ref = seed_topic(store, "Тема")
    a = reply(store, Fac([["А-1", "А-2", update("А-1А-2", [ADD])]]), ALICE, ref, ASK, T0)
    _step_to_first_delta(a)
    list(retry(store, Fac([["Б", update("Б")]]), ALICE, ref, T0))
    list(reply(store, Fac([[Down("down")]]), ALICE, ref, "В", T0))
    before = snapshot(store)
    list(a)
    assert snapshot(store) == before

    # (3) the mirror: A (reply) writes first, the delayed B (retry) is the late one
    store = new_store(tmp_path / "3")
    ref = seed_topic(store, "Тема")
    a = reply(store, Fac([["А-1", "А-2", update("А-1А-2")]]), ALICE, ref, ASK, T0)
    _step_to_first_delta(a)
    b = retry(store, Fac([["Б-1", "Б-2", update("Б-1Б-2", [ADD])]]), ALICE, ref, T0)
    _step_to_first_delta(b)
    list(a)
    before = snapshot(store)
    list(b)
    assert snapshot(store) == before

    # (4) the topic is deleted while A waits
    store = new_store(tmp_path / "4")
    ref = seed_topic(store, "Тема", [("Перше", "Перша відповідь")])
    a = reply(store, Fac([["А-1", "А-2", update("А-1А-2", [ADD])]]), ALICE, ref, ASK, T0)
    _step_to_first_delta(a)
    delete_topic(store, ALICE, ref)
    before = snapshot(store)
    list(a)
    assert snapshot(store) == before

    # (5) without a viewer, through the route: B and C happen while A waits for the latch
    root = tmp_path / "5"
    store = new_store(root)
    ref = seed_topic(store, "Тема")
    seen: dict[str, dict[str, bytes]] = {}

    def b_and_c() -> None:
        list(retry(store, Fac([["Б", update("Б")]]), ALICE, ref, T0))
        list(reply(store, Fac([["В-відповідь", update("В-відповідь")]]), ALICE, ref, "В", T0))
        seen["before"] = snapshot(store)

    fac = Fac([["А-1", WAIT, b_and_c, "А-2", update("А-1А-2", [ADD])]])
    app = make_app(root, store, fac)
    asgi_call(app, url(ref, "/reply"), "disconnect_after_delta", {"text": ASK}, fac.latch)
    assert "before" in seen
    assert snapshot(store) == seen["before"]


ADD = {"op": "add", "id": "i1", "type": "plan", "text": "кав'ярня", "turn": "t1"}


# --- I5 ------------------------------------------------------------------------------------------


def test_I5_when_no_one_changed_the_topic_the_answer_is_written_as_before(tmp_path: Path) -> None:
    add2 = {"op": "add", "id": "i2", "type": "goal", "text": "прибуток", "turn": "t3"}

    # (1) a fresh topic, reply read at once
    store = new_store(tmp_path / "1")
    ref = seed_topic(store, "Тема")
    events = list(reply(store, Fac([["Так", update("Так", [ADD])]]), ALICE, ref, ASK, T0))
    assert events[-1] == Answered(2)
    assert turns(store, ref) == [(1, "user", ASK), (2, "model", "Так")]
    assert [(i.id, i.text) for i in open_topic(store, ALICE, ref, T0).problem_map.items] == [
        ("i1", "кав'ярня")
    ]

    # (2) a topic with an exchange, the reply read lazily, with a pause after the first delta
    store = new_store(tmp_path / "2")
    ref = seed_topic(store, "Тема")
    list(reply(store, Fac([["Перша", update("Перша", [ADD])]]), ALICE, ref, "Перше", T0))
    a = reply(store, Fac([["Дру", "га", update("Друга", [add2])]]), ALICE, ref, ASK, T0)
    first = _step_to_first_delta(a)
    time.sleep(0.05)
    rest = list(a)
    assert first == [Saved(3), Delta("Дру")]
    assert rest == [Delta("га"), Answered(4)]
    assert turns(store, ref) == [
        (1, "user", "Перше"),
        (2, "model", "Перша"),
        (3, "user", ASK),
        (4, "model", "Друга"),
    ]
    assert [(i.id, i.text) for i in open_topic(store, ALICE, ref, T0).problem_map.items] == [
        ("i1", "кав'ярня"),
        ("i2", "прибуток"),
    ]

    # (3) retry of a pending turn after an exchange
    store = new_store(tmp_path / "3")
    ref = seed_topic(store, "Тема", [("Перше", "Перша")])
    make_pending(store, ref, ASK)
    events = list(retry(store, Fac([["Ще раз", update("Ще раз", [ADD])]]), ALICE, ref, T0))
    assert events == [Delta("Ще раз"), Answered(4)]
    assert turns(store, ref) == [
        (1, "user", "Перше"),
        (2, "model", "Перша"),
        (3, "user", ASK),
        (4, "model", "Ще раз"),
    ]
    assert [(i.id, i.text) for i in open_topic(store, ALICE, ref, T0).problem_map.items] == [
        ("i1", "кав'ярня")
    ]
