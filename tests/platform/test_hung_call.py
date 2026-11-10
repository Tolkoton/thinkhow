"""Bug 003 (task 313): a short structured Gemini call that hangs is given up within a minute, not after 300 s.

A Gemini that hangs sends no byte; httpx then waits the whole read timeout of the call's `http_options` and
raises `ReadTimeout`. The fake client below moves a fake clock by exactly that timeout, so the clock reads
how long the person waits with the production limits of `Settings`.
"""

import importlib
import sys
from pathlib import Path
from typing import Any

import httpx
from google.genai import types

from thinkhow.facilitation.deep import deep_research
from thinkhow.facilitation.route import route
from thinkhow.facilitation.types import ReplyDelta
from thinkhow.platform.config import Settings
from thinkhow.platform.llm import KnowledgeRev, VertexLlm

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "contract" / "fact_answer"))
fa: Any = importlib.import_module("fa_fakes")  # the fact-answer helpers: a context and a router answer

ANSWER_S = 4.0  # the third attempt answers as it did in production (604 s − 2 × 300 s)
BACKOFF_S = 3.0  # backoff_s(0) + backoff_s(1) is at most 1 + 2 s


class HangingGemini:
    """Hangs the first `hangs` calls for their whole read timeout, then answers `raw`."""

    def __init__(self, hangs: int, raw: str) -> None:
        self.now, self.hangs, self.raw = 0.0, hangs, raw
        self.models = self

    def generate_content(self, model: str, contents: Any, config: types.GenerateContentConfig) -> Any:
        if self.hangs:
            self.hangs -= 1
            assert config.http_options is not None and config.http_options.timeout is not None
            self.now += config.http_options.timeout / 1000
            raise httpx.ReadTimeout("no byte from Gemini")
        self.now += ANSWER_S
        part = types.Part(text=self.raw)
        return types.GenerateContentResponse(
            candidates=[types.Candidate(content=types.Content(parts=[part]))]
        )

    def sleep(self, seconds: float) -> None:
        self.now += seconds


def production_llm(client: HangingGemini) -> VertexLlm:
    settings = Settings(local=True)
    return VertexLlm(
        client,
        settings.model,
        settings.llm_timeout_s,
        settings.llm_attempts,
        client.sleep,
        lambda: client.now,
    )


def test_a_router_call_that_hangs_twice_is_given_up_within_a_minute_each_time() -> None:
    client = HangingGemini(hangs=2, raw=fa.answer_raw())
    got = route(fa.context(()), fa.knowledge(), production_llm(client))
    assert got.action == "answer"
    assert client.now <= 2 * 60 + BACKOFF_S + ANSWER_S, f"the person waited {client.now:.0f} s"


def test_a_deep_plan_call_that_hangs_twice_is_given_up_within_a_minute_each_time() -> None:
    plan = '{"intro": "Шукаю.", "questions": ["перше питання", "друге питання"]}'
    client = HangingGemini(hangs=2, raw=plan)
    steps = next(deep_research("питання", fa.context(()), production_llm(client), KnowledgeRev(3, 7)))
    assert isinstance(steps, ReplyDelta) and steps.text.startswith("Шукаю.")
    assert client.now <= 2 * 60 + BACKOFF_S + ANSWER_S, f"the person waited {client.now:.0f} s"
