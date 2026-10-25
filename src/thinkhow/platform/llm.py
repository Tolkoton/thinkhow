"""Gemini calls: timeouts, retries, structured output, the streamed reply field, one log line per call.

Vertex AI (google-genai) in production, a scripted double in tests and local mode (M3 A2, A4).
Does NOT build prompts or know any schema of the parts; the knowledge revision is opaque log data.
"""

import time
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from typing import Any, Literal, Protocol, TypeVar

from google.genai import types
from pydantic import BaseModel

from thinkhow.platform._reply_stream import ReplyExtractor
from thinkhow.platform._retry import backoff_s, retryable
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
class Source:
    title: str
    url: str


@dataclass(frozen=True)
class Found:
    """What the web search of one call found: its queries, its sources, Google's Search suggestions (HTML)."""

    queries: tuple[str, ...]
    sources: tuple[Source, ...]
    suggestions_html: str | None


@dataclass(frozen=True)
class Done:
    raw_json: str
    usage: Usage
    found: Found | None = None


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
FoundScript = Callable[[str, Sequence[Turn], type[BaseModel]], Found | None]


class _Attempt:
    """What one call learnt, for the log line: attempts made, usage, outcome."""

    def __init__(self, search: bool = False) -> None:
        self.attempts = 0
        self.usage = Usage(0, 0, 0)
        self.search = search
        self.found: Found | None = None


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
        search: bool = False,
    ) -> None:
        self.client = client
        self.search = search
        self.model = model
        self.timeout_s = timeout_s
        self.attempts = attempts
        self.sleep = sleep
        self.clock = clock

    def stream_json(
        self, system: str, contents: Sequence[Turn], schema: type[BaseModel], rev: KnowledgeRev | None
    ) -> Iterator[ReplyDelta | Done]:
        """Flow: up to `attempts` tries → stream deltas, gather what search found → one Done; one log line."""
        started, call = self.clock(), _Attempt(self.search)
        try:
            for attempt in range(self.attempts):
                call.attempts = attempt + 1
                shown = False
                try:
                    extractor, raw, gathered = ReplyExtractor(), [], _Gathered()
                    for chunk in self._open_stream(system, contents, schema, self.search):
                        piece = _chunk_text(chunk)
                        raw.append(piece)
                        call.usage = _usage(chunk.usage_metadata) or call.usage
                        gathered.add(chunk)
                        delta = extractor.feed(piece)
                        if delta:
                            shown = True
                            yield ReplyDelta(delta)
                except Exception as exc:
                    self._fail_or_wait(exc, attempt, shown)
                    continue
                call.found = gathered.found() if self.search else None
                self._log(call, started, rev, "ok")
                yield Done("".join(raw), call.usage, call.found)
                return
        except LlmUnavailable:
            self._log(call, started, rev, "unavailable")
            raise

    def generate_json(
        self, system: str, contents: Sequence[Turn], schema: type[M], rev: KnowledgeRev | None
    ) -> M:
        """Flow: try up to `attempts` times → validate against the schema; one log line."""
        started, call = self.clock(), _Attempt()
        try:
            for attempt in range(self.attempts):
                call.attempts = attempt + 1
                try:
                    response = self.client.models.generate_content(
                        model=self.model, contents=_contents(contents), config=self._config(system, schema)
                    )
                except Exception as exc:
                    self._fail_or_wait(exc, attempt, shown=False)
                    continue
                call.usage = _usage(response.usage_metadata) or call.usage
                self._log(call, started, rev, "ok")
                return schema.model_validate_json(_chunk_text(response))
            raise LlmUnavailable("no attempt was allowed")
        except LlmUnavailable:
            self._log(call, started, rev, "unavailable")
            raise

    def _open_stream(
        self, system: str, contents: Sequence[Turn], schema: type[BaseModel], search: bool
    ) -> Iterator[Any]:
        stream: Iterator[Any] = self.client.models.generate_content_stream(
            model=self.model, contents=_contents(contents), config=self._config(system, schema, search)
        )
        return stream

    def _config(
        self, system: str, schema: type[BaseModel], search: bool = False
    ) -> types.GenerateContentConfig:
        """The call's config; the search tool only when asked (only stream_json of a search instance asks)."""
        return types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json",
            response_json_schema=schema.model_json_schema(),
            http_options=types.HttpOptions(timeout=int(self.timeout_s * 1000)),
            tools=[types.Tool(enterprise_web_search=types.EnterpriseWebSearch())] if search else None,
        )

    def _fail_or_wait(self, exc: Exception, attempt: int, shown: bool) -> None:
        """Raise LlmUnavailable unless a retry is allowed; otherwise wait the backoff."""
        if shown or not retryable(exc) or attempt + 1 >= self.attempts:
            raise LlmUnavailable(f"the model did not answer: {type(exc).__name__}") from exc
        self.sleep(backoff_s(attempt))

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
            search=call.search,
            queries=len(call.found.queries) if call.found else 0,
        )


class _Gathered:
    """What search found over the chunks of one attempt: queries and sources united, the last suggestions."""

    def __init__(self) -> None:
        self.queries: dict[str, None] = {}
        self.sources: dict[str, Source] = {}
        self.suggestions: str | None = None

    def add(self, chunk: Any) -> None:
        for candidate in getattr(chunk, "candidates", None) or []:
            meta = getattr(candidate, "grounding_metadata", None)
            if meta is not None:
                self._add_meta(meta)

    def _add_meta(self, meta: Any) -> None:
        for query in getattr(meta, "web_search_queries", None) or []:
            self.queries.setdefault(query, None)
        for grounding in getattr(meta, "grounding_chunks", None) or []:
            source = _source(getattr(grounding, "web", None))
            if source is not None:
                self.sources.setdefault(source.url, source)
        html = getattr(getattr(meta, "search_entry_point", None), "rendered_content", None)
        if html:
            self.suggestions = html

    def found(self) -> Found | None:
        if not self.queries and not self.sources:
            return None
        return Found(tuple(self.queries), tuple(self.sources.values()), self.suggestions)


def _source(web: Any) -> Source | None:
    """A web chunk with a non-empty uri; its title, else its domain, else the url."""
    url = getattr(web, "uri", None)
    if not url:
        return None
    return Source(getattr(web, "title", None) or getattr(web, "domain", None) or url, url)


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

    def __init__(self, script: Script, chunk: int = 7, found_script: FoundScript | None = None) -> None:
        self.script = script
        self.chunk = chunk
        self.found_script = found_script
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
        found = self.found_script(system, contents, schema) if self.found_script else None
        yield Done(raw, Usage(0, 0, 0), found)

    def generate_json(
        self, system: str, contents: Sequence[Turn], schema: type[M], rev: KnowledgeRev | None
    ) -> M:
        return schema.model_validate_json(self._answer(system, contents, schema))

    def _answer(self, system: str, contents: Sequence[Turn], schema: type[BaseModel]) -> str:
        self.calls.append((system, list(contents), schema))
        return self.script(system, contents, schema)


def make_llm(
    settings: Settings, script: Script, search: bool = False, found_script: FoundScript | None = None
) -> Llm:
    if settings.local:
        return ScriptedLlm(script, found_script=found_script if search else None)
    from google import genai

    client = genai.Client(vertexai=True, project=settings.project, location=settings.location)
    return VertexLlm(client, settings.model, settings.llm_timeout_s, settings.llm_attempts, search=search)
