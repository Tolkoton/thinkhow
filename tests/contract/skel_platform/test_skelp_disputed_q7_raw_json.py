"""DISPUTED (Q7): Done.raw_json is the raw text exactly as it arrived (the chunks joined, nothing
trimmed or re-serialised). Not sealed until answered."""

import pytest
from pydantic import BaseModel
from skelp_fakes import Clock, FakeGenaiClient, LogCapture, Sleeps, install_log_capture

from thinkhow.platform.llm import Done, ScriptedLlm, Turn, VertexLlm


class Reply(BaseModel):
    reply: str
    phase: str


@pytest.fixture
def logs(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> LogCapture:
    return install_log_capture(monkeypatch, capsys)


def test_q7_done_raw_json_is_the_text_as_it_arrived(logs: LogCapture) -> None:
    raw = '{\n  "reply" : "Привіт \\u0410",\n  "phase": "p1"\n}\n'
    items = list(ScriptedLlm(lambda s, c, m: raw).stream_json("sys", [Turn("user", "hi")], Reply, None))
    assert isinstance(items[-1], Done) and items[-1].raw_json == raw
    client = FakeGenaiClient([[raw[:10], raw[10:20], raw[20:]]])
    llm = VertexLlm(client, "gemini-4-argon", 300.0, 3, sleep=Sleeps(), clock=Clock())
    items = list(llm.stream_json("sys", [Turn("user", "hi")], Reply, None))
    assert isinstance(items[-1], Done) and items[-1].raw_json == raw
