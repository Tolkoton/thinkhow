"""DISPUTED (Q1): the backoff exponent k counts from 0 for the first retry. Not sealed until answered."""

import pytest
from pydantic import BaseModel
from skelp_fakes import Clock, FakeGenaiClient, LogCapture, Sleeps, api_error, install_log_capture

from thinkhow.platform.llm import Turn, VertexLlm


class Reply(BaseModel):
    reply: str
    phase: str


@pytest.fixture
def logs(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> LogCapture:
    return install_log_capture(monkeypatch, capsys)


def test_q1_backoff_first_retry_waits_half_to_one_second_then_one_to_two(logs: LogCapture) -> None:
    ok = '{"reply": "x", "phase": "p1"}'
    client = FakeGenaiClient([[api_error(429)], [api_error(429)], [ok]])
    sleeps = Sleeps()
    llm = VertexLlm(client, "gemini-4-argon", 300.0, 3, sleep=sleeps, clock=Clock())
    list(llm.stream_json("sys", [Turn("user", "hi")], Reply, None))
    assert len(sleeps.delays) == 2
    assert 0.5 <= sleeps.delays[0] <= 1.0
    assert 1.0 <= sleeps.delays[1] <= 2.0
