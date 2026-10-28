"""Contract tests of finish-answer: the behaviours outside the invariants (slice tester)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fin_fakes import (
    ALICE,
    T0,
    WAIT,
    Down,
    Fac,
    Step,
    asgi_call,
    log_lines,
    make_app,
    new_store,
    seed_topic,
    turns,
    update,
)

from thinkhow.web.server import _stream
from thinkhow.workspace import (
    Answered,
    Delta,
    Failed,
    ReplyEvent,
    Saved,
    TopicRef,
    delete_topic,
    reply,
    retry,
)

ASK = "Хочу відкрити кав'ярню."


def url(ref: TopicRef, tail: str) -> str:
    return f"/topics/{ref.uid}/{ref.topic_id}{tail}"


def _step_to_first_delta(events: Iterator[ReplyEvent]) -> None:
    for event in events:
        if isinstance(event, Delta):
            return
    raise AssertionError("no delta before the end")


def _named(out: str, *names: str) -> list[dict[str, object]]:
    return [line for line in log_lines(out) if line.get("event") in names]


def test_a_superseded_answer_gives_failed_superseded_and_logs_reply_superseded_not_reply_failed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # (1) B (retry) answers turn 1 and the person writes C with its answer while A waits
    store = new_store(tmp_path / "1")
    ref = seed_topic(store, "Тема")
    a = reply(store, Fac([["А-1", "А-2", update("А-1А-2")]]), ALICE, ref, ASK, T0)
    _step_to_first_delta(a)
    list(retry(store, Fac([["Б", update("Б")]]), ALICE, ref, T0))
    list(reply(store, Fac([["В-відповідь", update("В-відповідь")]]), ALICE, ref, "В", T0))
    capsys.readouterr()
    rest = list(a)
    out = capsys.readouterr().out
    assert rest[-1] == Failed("Superseded")
    assert not any(isinstance(e, Answered) for e in rest)
    lines = _named(out, "reply_superseded")
    assert len(lines) == 1
    assert lines[0]["uid"] == ALICE.id and lines[0]["topic_id"] == ref.topic_id and "turn" in lines[0]
    assert _named(out, "reply_failed", "stream_error") == []

    # (2) the mirror: A (reply) writes first, the delayed B (retry) is superseded, A's answer stays
    store = new_store(tmp_path / "2")
    ref = seed_topic(store, "Тема")
    a = reply(store, Fac([["А-1", "А-2", update("А-1А-2")]]), ALICE, ref, ASK, T0)
    _step_to_first_delta(a)
    b = retry(store, Fac([["Б-1", "Б-2", update("Б-1Б-2")]]), ALICE, ref, T0)
    _step_to_first_delta(b)
    assert list(a)[-1] == Answered(2)
    capsys.readouterr()
    rest = list(b)
    out = capsys.readouterr().out
    assert rest[-1] == Failed("Superseded")
    assert turns(store, ref) == [(1, "user", ASK), (2, "model", "А-1А-2")]
    lines = _named(out, "reply_superseded")
    assert len(lines) == 1
    assert lines[0]["uid"] == ALICE.id and lines[0]["topic_id"] == ref.topic_id and "turn" in lines[0]
    assert _named(out, "reply_failed", "stream_error") == []

    # (3) the topic is deleted while A waits: the same line and reason, no TopicNotFound let out
    store = new_store(tmp_path / "3")
    ref = seed_topic(store, "Тема")
    a = reply(store, Fac([["А-1", "А-2", update("А-1А-2")]]), ALICE, ref, ASK, T0)
    _step_to_first_delta(a)
    delete_topic(store, ALICE, ref)
    capsys.readouterr()
    rest = list(a)
    out = capsys.readouterr().out
    assert rest[-1] == Failed("Superseded")
    lines = _named(out, "reply_superseded")
    assert len(lines) == 1
    assert lines[0]["uid"] == ALICE.id and lines[0]["topic_id"] == ref.topic_id and "turn" in lines[0]
    assert _named(out, "reply_failed", "stream_error") == []


def test_without_a_viewer_a_failure_of_the_answer_is_a_log_line_and_the_call_still_returns(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    store = new_store(tmp_path)
    fac = Fac([["Так", WAIT, Down("model down")]])
    app = make_app(tmp_path, store, fac)
    ref = seed_topic(store, "Тема")
    capsys.readouterr()
    asgi_call(app, url(ref, "/reply"), "disconnect_after_delta", {"text": ASK}, fac.latch)
    out = capsys.readouterr().out
    assert _named(out, "reply_failed", "stream_error"), "no log line of the failure without a viewer"
    assert turns(store, ref) == [(1, "user", ASK)]


def test_a_disconnect_is_not_an_error_and_logs_nothing_new(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    script: list[Step] = ["Так", WAIT, ", так", update("Так, так")]

    store = new_store(tmp_path / "read")
    fac = Fac([list(script)])
    fac.latch.set()
    app = make_app(tmp_path / "read", store, fac)
    ref = seed_topic(store, "Тема")
    capsys.readouterr()
    asgi_call(app, url(ref, "/reply"), "read_all", {"text": ASK})
    read_lines = log_lines(capsys.readouterr().out)

    store = new_store(tmp_path / "gone")
    fac = Fac([list(script)])
    app = make_app(tmp_path / "gone", store, fac)
    ref = seed_topic(store, "Тема")
    capsys.readouterr()
    asgi_call(app, url(ref, "/reply"), "disconnect_after_delta", {"text": ASK}, fac.latch)
    gone_lines = log_lines(capsys.readouterr().out)

    assert {str(line.get("event")) for line in gone_lines} <= {str(line.get("event")) for line in read_lines}
    assert [line for line in gone_lines if line.get("severity") not in ("INFO", "DEBUG", None)] == []


def test_the_response_of_stream_keeps_its_media_type_and_headers() -> None:
    events: Iterator[ReplyEvent] = iter([Saved(1), Delta("а"), Answered(2)])
    call = asgi_call(_stream(events), "/x", "read_all")
    start = call.start
    assert start is not None and start["status"] == 200
    headers = {k.decode().lower(): v.decode() for k, v in start["headers"]}
    assert headers["content-type"].startswith("text/event-stream")
    assert headers["cache-control"] == "no-cache"
    assert headers["x-accel-buffering"] == "no"
