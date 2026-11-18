"""Task 752: the limits of the facilitator's stream, the deep search and the step recognizer, set from the
measurements of `llm_call` (task 744) — a hung call is given up sooner, a thinking one is not cut.

A Gemini that hangs sends no byte; httpx then waits the whole read timeout of the call's `http_options`
and raises `ReadTimeout`. The fake client moves a fake clock by the time a call takes, or by that timeout
when it is shorter, so the clock reads how long the person waits with the production limits of `Settings`.
"""

import importlib
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from google.genai import types
from pydantic import BaseModel

from thinkhow.facilitation.answer import answer_fact
from thinkhow.facilitation.respond import _routed, answer_schema
from thinkhow.facilitation.steps import recognize_step
from thinkhow.facilitation.types import FactAnswer
from thinkhow.platform.config import Settings
from thinkhow.platform.llm import KnowledgeRev, Turn, VertexLlm

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "contract" / "fact_answer"))
fa: Any = importlib.import_module("fa_fakes")  # the fact-answer helpers: a context, a knowledge, the cards

ANSWER_S = 4.0
BACKOFF_S = 3.0  # backoff_s(0) + backoff_s(1) is at most 1 + 2 s
LONGEST_STREAM_S = 119.3  # the longest stream measured, start to last chunk (bug 003, Cloud Logging)
LONGEST_SEARCH_S = 180.6  # the longest search that answered on its first attempt (bug 003)
HUNG = 10_000.0  # a call that never answers
FACT = '{"reply": "Відповідь.", "map_updates": []}'
UPDATE = '{"reply": "Відповідь.", "current_phase_id": null, "phase_exit_met": false, "map_updates": []}'
STEP = '{"answered": true, "outcome": "worked", "clearer": "yes", "said": "вийшло"}'


def response(text: str) -> types.GenerateContentResponse:
    part = types.Part(text=text)
    return types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(parts=[part]))])


class SlowGemini:
    """Each call takes the next of `takes_s` seconds (a stream: before its first chunk) — or its whole read
    timeout and a `ReadTimeout`, when that is shorter."""

    def __init__(self, raw: str, takes_s: list[float]) -> None:
        self.now, self.raw, self.takes_s = 0.0, raw, list(takes_s)
        self.models = self

    def generate_content(self, model: str, contents: Any, config: types.GenerateContentConfig) -> Any:
        self._wait(config)
        return response(self.raw)

    def generate_content_stream(self, model: str, contents: Any, config: types.GenerateContentConfig) -> Any:
        return self._chunks(config)

    def _chunks(self, config: types.GenerateContentConfig) -> Iterator[Any]:
        self._wait(config)
        yield response(self.raw[:5])
        yield response(self.raw[5:])

    def _wait(self, config: types.GenerateContentConfig) -> None:
        assert config.http_options is not None and config.http_options.timeout is not None
        limit_s = config.http_options.timeout / 1000
        takes_s = self.takes_s.pop(0)
        if takes_s >= limit_s:
            self.now += limit_s
            raise httpx.ReadTimeout("no byte from Gemini")
        self.now += takes_s

    def sleep(self, seconds: float) -> None:
        self.now += seconds


def production_llm(client: SlowGemini) -> VertexLlm:
    settings = Settings(local=True)
    return VertexLlm(
        client,
        settings.model,
        settings.llm_timeout_s,
        settings.llm_attempts,
        client.sleep,
        lambda: client.now,
    )


def facilitator_schemas() -> list[type[BaseModel]]:
    return [answer_schema(fa.ALPHA), _routed(fa.ALPHA)[0]]


def test_a_fact_answer_whose_first_chunk_never_comes_is_given_up_after_three_minutes_each_time() -> None:
    client = SlowGemini(FACT, [HUNG, HUNG, ANSWER_S])
    list(answer_fact(fa.context(()), fa.knowledge(), production_llm(client)))
    assert client.now <= 2 * 180 + BACKOFF_S + ANSWER_S, f"the person waited {client.now:.0f} s"


@pytest.mark.parametrize("schema", facilitator_schemas(), ids=lambda s: s.__name__)
def test_a_facilitator_stream_whose_first_chunk_never_comes_is_given_up_after_three_minutes(
    schema: type[BaseModel],
) -> None:
    client = SlowGemini(UPDATE, [HUNG, ANSWER_S])
    list(production_llm(client).stream_json("sys", [Turn("user", "питання")], schema, None))
    assert client.now <= 180 + BACKOFF_S + ANSWER_S, f"the person waited {client.now:.0f} s"


@pytest.mark.parametrize("schema", [FactAnswer, *facilitator_schemas()], ids=lambda s: s.__name__)
def test_a_stream_as_long_as_the_longest_measured_is_not_cut(schema: type[BaseModel]) -> None:
    client = SlowGemini(UPDATE, [LONGEST_STREAM_S * 1.5])
    list(production_llm(client).stream_json("sys", [Turn("user", "питання")], schema, None))
    assert client.now == pytest.approx(LONGEST_STREAM_S * 1.5)


def test_a_search_that_hangs_is_given_up_after_four_minutes() -> None:
    client = SlowGemini("знайдено", [HUNG, ANSWER_S])
    text, _ = production_llm(client).search_text("sys", "питання", KnowledgeRev(3, 7))
    assert text == "знайдено"
    assert client.now <= 240 + BACKOFF_S + ANSWER_S, f"the person waited {client.now:.0f} s"


def test_a_search_as_long_as_the_longest_measured_is_not_cut() -> None:
    client = SlowGemini("знайдено", [LONGEST_SEARCH_S * 1.3])
    text, _ = production_llm(client).search_text("sys", "питання", KnowledgeRev(3, 7))
    assert text == "знайдено"
    assert client.now == pytest.approx(LONGEST_SEARCH_S * 1.3)


def test_a_step_recognition_that_hangs_twice_is_given_up_within_a_minute_each_time() -> None:
    client = SlowGemini(STEP, [HUNG, HUNG, ANSWER_S])
    got = recognize_step("крок", "Як вийшло?", "Вийшло.", production_llm(client))
    assert got.outcome == "worked"
    assert client.now <= 2 * 60 + BACKOFF_S + ANSWER_S, f"the person waited {client.now:.0f} s"
