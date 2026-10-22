"""Contract tests of skel-platform: log.py (slice tester; written from the contract, not the code)."""

import contextvars
import io
import json
from collections.abc import Callable

from thinkhow.platform.log import log_event, request_id


def _in_context(value: str | None, fn: Callable[[], None]) -> None:
    ctx = contextvars.copy_context()

    def run() -> None:
        request_id.set(value)
        fn()

    ctx.run(run)


def test_log_event_writes_one_json_line_per_event() -> None:
    stream = io.StringIO()
    log_event("card_saved", stream=stream, cards=3)
    log_event("card_saved", stream=stream, cards=4)
    lines = stream.getvalue().splitlines()
    assert len(lines) == 2
    first, second = (json.loads(line) for line in lines)
    assert first["severity"] == "INFO"
    assert first["event"] == "card_saved"
    assert first["request_id"] is None
    assert first["cards"] == 3
    assert second["cards"] == 4


def test_log_event_carries_the_request_id_of_the_context() -> None:
    stream = io.StringIO()
    _in_context("req-42", lambda: log_event("ping", stream=stream))
    assert json.loads(stream.getvalue())["request_id"] == "req-42"


def test_severity_can_be_given_as_a_field() -> None:
    stream = io.StringIO()
    log_event("boom", stream=stream, severity="ERROR")
    line = json.loads(stream.getvalue())
    assert line["severity"] == "ERROR"
    assert line["event"] == "boom"


def test_request_id_of_the_context_wins_over_a_field_of_the_same_name() -> None:
    stream = io.StringIO()
    _in_context("req-real", lambda: log_event("ping", stream=stream, request_id="spoofed"))
    assert json.loads(stream.getvalue())["request_id"] == "req-real"
