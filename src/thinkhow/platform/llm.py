"""Gemini calls: timeouts, retries, structured output, the streamed reply field, one log line per call.

Vertex AI (google-genai) in production, a scripted double in tests and local mode (M3 A2, A4).
Does NOT build prompts or know any schema of the parts; the knowledge revision is opaque log data.
"""

import random
import time
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from typing import Any, Literal, Protocol, TypeVar

import httpx
import httpx2
from google.genai import errors, types
from pydantic import BaseModel

from thinkhow.platform._reply_stream import ReplyExtractor
from thinkhow.platform.config import Settings
from thinkhow.platform.log import log_event

M = TypeVar("M", bound=BaseModel)


@dataclass(frozen=True)
class Turn:
    role: Literal["user", "model"]
    text: str


@dataclass(frozen=True)
class KnowledgeRev:
    rev: int
    n: int


@dataclass(frozen=True)
class ReplyDelta:
    text: str


@dataclass(frozen=True)
class Usage:
    prompt_tokens: int
    output_tokens: int
    thought_tokens: int


@dataclass(frozen=True)
class Done:
    raw_json: str
    usage: Usage


class LlmUnavailable(Exception):
    """The model did not answer after the retries, or the stream broke."""


class Llm(Protocol):
    def stream_json(
        self, system: str, contents: Sequence[Turn], schema: type[BaseModel], rev: KnowledgeRev | None
    ) -> Iterator[ReplyDelta | Done]: ...

    def generate_json(
        self, system: str, contents: Sequence[Turn], schema: type[M], rev: KnowledgeRev | None
    ) -> M: ...


Script = Callable[[str, Sequence[Turn], type[BaseModel]], str]


class _Attempt:
    """What one call learnt, for the log line: attempts made, usage, outcome."""

    def __init__(self) -> None:
        self.attempts = 0
        self.usage = Usage(0, 0, 0)


class VertexLlm:
    """Gemini on Vertex AI. Retries only before the first reply text reaches the caller (contract Q3, Q3a)."""

    def __init__(
        self,
        client: Any,
        model: str,
        timeout_s: float,
        attempts: int,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.client = client
        self.model = model
        self.timeout_s = timeout_s
        self.attempts = attempts
        self.sleep = sleep
        self.clock = clock

    def stream_json(
        self, system: str, contents: Sequence[Turn], schema: type[BaseModel], rev: KnowledgeRev | None
    ) -> Iterator[ReplyDelta | Done]:
        """Flow: try up to `attempts` times → stream deltas → one Done; one log line either way."""
        started, call = self.clock(), _Attempt()
        try:
            for attempt in range(self.attempts):
                call.attempts = attempt + 1
                shown = False
                try:
                    extractor, raw = ReplyExtractor(), []
                    for chunk in self._open_stream(system, contents, schema):
                        piece = _chunk_text(chunk)
                        raw.append(piece)
                        call.usage = _usage(chunk.usage_metadata) or call.usage
                        delta = extractor.feed(piece)
                        if delta:
                            shown = True
                            yield ReplyDelta(delta)
                except Exception as exc:
                    self._fail_or_wait(exc, attempt, shown)
                    continue
                self._log(call, started, rev, "ok")
                yield Done("".join(raw), call.usage)
                return
        except LlmUnavailable:
            self._log(call, started, rev, "unavailable")
            raise

    def generate_json(
        self, system: str, contents: Sequence[Turn], schema: type[M], rev: KnowledgeRev | None
    ) -> M:
        """Flow: try up to `attempts` times → validate against the schema; one log line."""
        started, call = self.clock(), _Attempt()
        response = None
        try:
            for attempt in range(self.attempts):
                call.attempts = attempt + 1
                try:
                    response = self.client.models.generate_content(
                        model=self.model, contents=_contents(contents), config=self._config(system, schema)
                    )
                    break
                except Exception as exc:
                    self._fail_or_wait(exc, attempt, shown=False)
        except LlmUnavailable:
            self._log(call, started, rev, "unavailable")
            raise
        call.usage = _usage(response.usage_metadata) or call.usage
        self._log(call, started, rev, "ok")
        return schema.model_validate_json(_chunk_text(response))

    def _open_stream(self, system: str, contents: Sequence[Turn], schema: type[BaseModel]) -> Iterator[Any]:
        stream: Iterator[Any] = self.client.models.generate_content_stream(
            model=self.model, contents=_contents(contents), config=self._config(system, schema)
        )
        return stream

    def _config(self, system: str, schema: type[BaseModel]) -> types.GenerateContentConfig:
        return types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json",
            response_json_schema=schema.model_json_schema(),
            http_options=types.HttpOptions(timeout=int(self.timeout_s * 1000)),
        )

    def _fail_or_wait(self, exc: Exception, attempt: int, shown: bool) -> None:
        """Raise LlmUnavailable unless a retry is allowed; otherwise wait the backoff."""
        if shown or not _retryable(exc) or attempt + 1 >= self.attempts:
            raise LlmUnavailable(f"the model did not answer: {type(exc).__name__}") from exc
        self.sleep(min(2**attempt, 30) * random.uniform(0.5, 1.0))

    def _log(self, call: _Attempt, started: float, rev: KnowledgeRev | None, outcome: str) -> None:
        log_event(
            "llm_call",
            severity="INFO" if outcome == "ok" else "WARNING",
            model=self.model,
            prompt_tokens=call.usage.prompt_tokens,
            output_tokens=call.usage.output_tokens,
            thought_tokens=call.usage.thought_tokens,
            latency_ms=int((self.clock() - started) * 1000),
            attempts=call.attempts,
            rev=rev.rev if rev else None,
            n=rev.n if rev else None,
            outcome=outcome,
        )


def _retryable(exc: Exception) -> bool:
    if isinstance(exc, (httpx.TimeoutException, httpx2.TimeoutException)):
        return True
    return isinstance(exc, errors.APIError) and (exc.code == 429 or exc.code >= 500)


def _contents(turns: Sequence[Turn]) -> list[types.Content]:
    return [types.Content(role=t.role, parts=[types.Part(text=t.text)]) for t in turns]


def _chunk_text(response: Any) -> str:
    """The answer text of a response or a stream chunk, thought parts left out."""
    parts = []
    for candidate in response.candidates or []:
        for part in (candidate.content.parts if candidate.content else None) or []:
            if part.text and not part.thought:
                parts.append(part.text)
    return "".join(parts)


def _usage(meta: Any) -> Usage | None:
    if meta is None:
        return None
    return Usage(
        prompt_tokens=meta.prompt_token_count or 0,
        output_tokens=meta.candidates_token_count or 0,
        thought_tokens=meta.thoughts_token_count or 0,
    )


class ScriptedLlm:
    """The double: the script's JSON, cut into `chunk`-sized pieces, through the same delta extraction."""

    def __init__(self, script: Script, chunk: int = 7) -> None:
        self.script = script
        self.chunk = chunk
        self.calls: list[tuple[str, list[Turn], type[BaseModel]]] = []

    def stream_json(
        self, system: str, contents: Sequence[Turn], schema: type[BaseModel], rev: KnowledgeRev | None
    ) -> Iterator[ReplyDelta | Done]:
        raw = self._answer(system, contents, schema)
        extractor = ReplyExtractor()
        for start in range(0, len(raw), self.chunk):
            delta = extractor.feed(raw[start : start + self.chunk])
            if delta:
                yield ReplyDelta(delta)
        yield Done(raw, Usage(0, 0, 0))

    def generate_json(
        self, system: str, contents: Sequence[Turn], schema: type[M], rev: KnowledgeRev | None
    ) -> M:
        return schema.model_validate_json(self._answer(system, contents, schema))

    def _answer(self, system: str, contents: Sequence[Turn], schema: type[BaseModel]) -> str:
        self.calls.append((system, list(contents), schema))
        return self.script(system, contents, schema)


def make_llm(settings: Settings, script: Script) -> Llm:
    if settings.local:
        return ScriptedLlm(script)
    from google import genai

    client = genai.Client(vertexai=True, project=settings.project, location=settings.location)
    return VertexLlm(client, settings.model, settings.llm_timeout_s, settings.llm_attempts)
