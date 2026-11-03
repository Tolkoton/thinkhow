"""Catch-up contract tests of finish-answer (slice tester, from the contract only): the behaviours of the
«Errors» line of the Seam that the first hand-in did not hold on their own."""

from __future__ import annotations

import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from fin_fakes import (
    ALICE,
    T0,
    Boom,
    Fac,
    asgi_call,
    log_lines,
    make_app,
    new_store,
    seed_topic,
    snapshot,
    sse_events,
    update,
)

from thinkhow.web.server import _stream
from thinkhow.workspace import Delta, ReplyEvent, Saved, TopicRef, reply, retry

ASK = "Хочу відкрити кав'ярню."


def url(ref: TopicRef, tail: str) -> str:
    return f"/topics/{ref.uid}/{ref.topic_id}{tail}"


def breaking() -> Iterator[ReplyEvent]:
    yield Saved(1)
    time.sleep(0.05)
    yield Delta("а")
    time.sleep(0.2)
    raise Boom("mid-stream")


def test_an_exception_in_the_events_gives_a_reading_client_failed_internal_and_logs_stream_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    capsys.readouterr()
    body = asgi_call(_stream(breaking()), "/x", "read_all").body.decode()
    out = capsys.readouterr().out
    assert sse_events(body) == [
        ("saved", {"turn": 1}),
        ("delta", {"text": "а"}),
        ("failed", {"reason": "Internal"}),
    ]
    assert [line for line in log_lines(out) if line.get("event") == "stream_error"], "no stream_error line"


def test_without_a_viewer_an_exception_in_the_events_is_only_a_stream_error_line(
    capsys: pytest.CaptureFixture[str],
) -> None:
    for mode in ("disconnect_at_once", "disconnect_after_delta"):
        capsys.readouterr()
        asgi_call(_stream(breaking()), "/x", mode)  # returns: the failure does not hang the call
        out = capsys.readouterr().out
        assert [line for line in log_lines(out) if line.get("event") == "stream_error"], mode


def test_a_live_client_of_a_superseded_answer_sees_failed_superseded_and_the_topic_is_kept(
    tmp_path: Path,
) -> None:
    store = new_store(tmp_path)
    ref = seed_topic(store, "Тема")
    seen: dict[str, dict[str, bytes]] = {}

    def b_and_c() -> None:
        list(retry(store, Fac([["Б", update("Б")]]), ALICE, ref, T0))
        list(reply(store, Fac([["В-відповідь", update("В-відповідь")]]), ALICE, ref, "В", T0))
        seen["before"] = snapshot(store)

    fac = Fac([["А-1", b_and_c, "А-2", update("А-1А-2")]])
    app = make_app(tmp_path, store, fac)
    body = asgi_call(app, url(ref, "/reply"), "read_all", {"text": ASK}).body.decode()
    events = sse_events(body)
    assert events[0] == ("saved", {"turn": 1})
    assert events[-1] == ("failed", {"reason": "Superseded"})
    assert all(name != "answered" for name, _ in events)
    assert snapshot(store) == seen["before"]
