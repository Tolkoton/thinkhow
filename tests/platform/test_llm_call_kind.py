"""Task 744: the `llm_call` line names the call's kind and, for a stream, the time to its first chunk.

The limits of the facilitator's stream and of the deep search are set from these measurements a week later:
a stream's httpx limit is a limit between chunks, and before the first chunk the model thinks.
"""

import json
from collections.abc import Iterator
from typing import Any

import httpx
import pytest
from google.genai import types

from thinkhow.facilitation.types import DeepPlan, StepOutcome
from thinkhow.platform.llm import Turn, VertexLlm

TURNS = [Turn("user", "питання")]
PLAN = '{"intro": "Шукаю.", "questions": ["перше питання", "друге питання"]}'
STEP = '{"answered": true, "outcome": "worked", "clearer": "yes", "said": "вийшло"}'


def response(text: str) -> types.GenerateContentResponse:
    part = types.Part(text=text)
    return types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(parts=[part]))])


class TimedGemini:
    """A Gemini on a fake clock: a stream thinks `think_s` before its first chunk, each chunk takes 1 s."""

    def __init__(self, raw: str, think_s: float = 0.0, hung_streams: int = 0) -> None:
        self.now, self.raw, self.think_s, self.hung_streams = 0.0, raw, think_s, hung_streams
        self.models = self

    def generate_content_stream(self, model: str, contents: Any, config: Any) -> Iterator[Any]:
        return self._chunks()

    def _chunks(self) -> Iterator[Any]:
        self.now += self.think_s
        if self.hung_streams:
            self.hung_streams -= 1
            raise httpx.ReadTimeout("no chunk from Gemini")
        for piece in (self.raw[:5], self.raw[5:]):
            yield response(piece)
            self.now += 1.0

    def generate_content(self, model: str, contents: Any, config: Any) -> Any:
        self.now += 4.0
        return response(self.raw)


def llm(client: TimedGemini) -> VertexLlm:
    return VertexLlm(client, "gemini-4-argon", 300.0, 3, sleep=lambda s: None, clock=lambda: client.now)


def calls(capsys: pytest.CaptureFixture[str]) -> list[dict[str, Any]]:
    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.startswith("{")]
    return [line for line in lines if line["event"] == "llm_call"]


def test_a_stream_logs_its_schema_as_the_kind_and_the_time_to_its_first_chunk(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = TimedGemini(PLAN, think_s=37.25)
    list(llm(client).stream_json("sys", TURNS, DeepPlan, None))
    [line] = calls(capsys)
    assert line["kind"] == "DeepPlan"
    assert line["first_chunk_ms"] == 37250
    assert line["latency_ms"] == 39250


def test_the_time_to_the_first_chunk_is_that_of_the_attempt_that_answered(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = TimedGemini(PLAN, think_s=20.0, hung_streams=1)
    list(llm(client).stream_json("sys", TURNS, DeepPlan, None))
    [line] = calls(capsys)
    assert line["attempts"] == 2
    assert line["first_chunk_ms"] == 20000


def test_a_call_without_a_stream_logs_its_kind_and_no_first_chunk(capsys: pytest.CaptureFixture[str]) -> None:
    client = TimedGemini(STEP)
    llm(client).generate_json("sys", TURNS, StepOutcome, None)
    llm(client).search_text("sys", "питання", None)
    step, search = calls(capsys)
    assert (step["kind"], step["first_chunk_ms"]) == ("StepOutcome", None)
    assert (search["kind"], search["first_chunk_ms"]) == ("search", None)
