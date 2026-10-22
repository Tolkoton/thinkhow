"""DISPUTED (Q2): Usage.output_tokens is the SDK's candidates_token_count (thought tokens apart).
Not sealed until answered."""

import pytest
from pydantic import BaseModel
from skelp_fakes import Clock, FakeGenaiClient, LogCapture, Sleeps, install_log_capture

from thinkhow.platform.llm import Done, Turn, Usage, VertexLlm


class Reply(BaseModel):
    reply: str
    phase: str


@pytest.fixture
def logs(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> LogCapture:
    return install_log_capture(monkeypatch, capsys)


def test_q2_done_usage_and_log_tokens_map_prompt_candidates_thoughts(logs: LogCapture) -> None:
    # the fake's last chunk: prompt_token_count=11, candidates_token_count=7, thoughts_token_count=5
    raw = '{"reply": "x", "phase": "p1"}'
    client = FakeGenaiClient([[raw[:8], raw[8:]]])
    llm = VertexLlm(client, "gemini-4-argon", 300.0, 3, sleep=Sleeps(), clock=Clock())
    items = list(llm.stream_json("sys", [Turn("user", "hi")], Reply, None))
    done = items[-1]
    assert isinstance(done, Done)
    assert done.usage == Usage(prompt_tokens=11, output_tokens=7, thought_tokens=5)
    [line] = logs.events("llm_call")
    assert line["output_tokens"] == 7
