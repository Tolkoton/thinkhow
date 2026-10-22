"""Fakes for the skel-platform contract tests (slice tester). Built from the contract, not the code.

- FakeGenaiClient: an object with `models.generate_content_stream` and `models.generate_content`.
  As the real SDK, a failing STREAM is a generator that raises on its first `next()`, not on the call
  (contract, Seam 2). A failing non-streaming call raises on the call, as the real SDK does.
- FakeGcsClient: buckets and blobs in memory; `upload_from_string(..., if_generation_match=0)` raises
  `PreconditionFailed` when the object exists (contract, Seam 3).
- LogCapture: every JSON line written by `thinkhow.platform.log.log_event` (default stream redirected)
  or printed to stdout.
"""

from __future__ import annotations

import io
import json
from collections.abc import Iterator
from typing import Any

from google.api_core.exceptions import NotFound, PreconditionFailed
from google.genai import errors, types

# ------------------------------------------------------------------ genai


def api_error(code: int) -> errors.APIError:
    body = {"error": {"code": code, "message": f"fake {code}", "status": "FAKE"}}
    if code >= 500:
        return errors.ServerError(code, body)
    return errors.ClientError(code, body)


USAGE = types.GenerateContentResponseUsageMetadata(
    prompt_token_count=11, candidates_token_count=7, thoughts_token_count=5
)


def chunk(
    text: str, usage: types.GenerateContentResponseUsageMetadata | None = None
) -> types.GenerateContentResponse:
    return types.GenerateContentResponse(
        candidates=[types.Candidate(content=types.Content(role="model", parts=[types.Part(text=text)]))],
        usage_metadata=usage,
    )


class FakeModels:
    def __init__(self, plans: list[list[Any]]) -> None:
        # one plan per call: a list of str (a chunk of text) or BaseException (raised at that point)
        self.plans = list(plans)
        self.calls: list[dict[str, Any]] = []
        self.last_chunk_pulled = False

    def _next_plan(self, kwargs: dict[str, Any]) -> list[Any]:
        self.calls.append(kwargs)
        if not self.plans:
            raise AssertionError("the fake client was called more times than the test planned")
        return self.plans.pop(0)

    def generate_content_stream(self, *args: Any, **kwargs: Any) -> Iterator[types.GenerateContentResponse]:
        plan = self._next_plan(kwargs)
        return self._stream(plan)

    def _stream(self, plan: list[Any]) -> Iterator[types.GenerateContentResponse]:
        texts = [step for step in plan if isinstance(step, str)]
        sent = 0
        for step in plan:
            if isinstance(step, BaseException):
                raise step
            sent += 1
            last = sent == len(texts) and not isinstance(plan[-1], BaseException)
            if last:
                self.last_chunk_pulled = True
            yield chunk(step, USAGE if last else None)

    def generate_content(self, *args: Any, **kwargs: Any) -> types.GenerateContentResponse:
        plan = self._next_plan(kwargs)
        for step in plan:
            if isinstance(step, BaseException):
                raise step
        return chunk("".join(plan), USAGE)


class FakeGenaiClient:
    def __init__(self, plans: list[list[Any]]) -> None:
        self.models = FakeModels(plans)

    @property
    def calls(self) -> list[dict[str, Any]]:
        return self.models.calls


def cfg_get(config: Any, name: str) -> Any:
    if config is None:
        return None
    if isinstance(config, dict):
        return config.get(name)
    return getattr(config, name, None)


class Sleeps:
    def __init__(self) -> None:
        self.delays: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.delays.append(seconds)


class Clock:
    """The first reading is 10.0 s, every later one 12.5 s: a call measured from its start lasts 2500 ms."""

    def __init__(self) -> None:
        self.readings = 0

    def __call__(self) -> float:
        self.readings += 1
        return 10.0 if self.readings == 1 else 12.5


# ------------------------------------------------------------------ GCS


def _api_exc(kind: Any, message: str) -> Exception:
    """google.api_core's exception constructors are untyped; build them through one typed door."""
    exc: Exception = kind(message)
    return exc


class FakeBlob:
    def __init__(self, bucket: FakeBucket, name: str) -> None:
        self.bucket = bucket
        self.name = name
        self.content_type: str | None = None

    def _io(self, op: str, **kw: Any) -> None:
        self.bucket.client.io.append((op, self.bucket.name, self.name, kw))

    def upload_from_string(self, data: Any, content_type: str | None = None, **kwargs: Any) -> None:
        self._io("upload", content_type=content_type or self.content_type, **kwargs)
        gm = kwargs.get("if_generation_match")
        if gm == 0 and (self.name in self.bucket.objects or self.name in self.bucket.racing):
            raise _api_exc(PreconditionFailed, "fake: object exists")
        self.bucket.objects[self.name] = data.encode() if isinstance(data, str) else bytes(data)

    def download_as_bytes(self, *args: Any, **kwargs: Any) -> bytes:
        self._io("download")
        if self.name not in self.bucket.objects:
            raise _api_exc(NotFound, "fake: no such object")
        return self.bucket.objects[self.name]

    def download_as_string(self, *args: Any, **kwargs: Any) -> bytes:
        return self.download_as_bytes()

    def exists(self, *args: Any, **kwargs: Any) -> bool:
        self._io("exists")
        return self.name in self.bucket.objects

    def reload(self, *args: Any, **kwargs: Any) -> None:
        self._io("reload")
        if self.name not in self.bucket.objects:
            raise _api_exc(NotFound, "fake: no such object")


class FakeBucket:
    def __init__(self, client: FakeGcsClient, name: str) -> None:
        self.client = client
        self.name = name
        self.objects: dict[str, bytes] = {}
        self.racing: set[str] = set()  # absent to every read, but created by someone else before the upload

    def blob(self, name: str, *args: Any, **kwargs: Any) -> FakeBlob:
        return FakeBlob(self, name)

    def get_blob(self, name: str, *args: Any, **kwargs: Any) -> FakeBlob | None:
        self.client.io.append(("get_blob", self.name, name, {}))
        return FakeBlob(self, name) if name in self.objects else None

    def list_blobs(self, prefix: str | None = None, **kwargs: Any) -> list[FakeBlob]:
        self.client.io.append(("list", self.name, prefix, kwargs))
        names = [n for n in self.objects if n.startswith(prefix or "")]
        return [FakeBlob(self, n) for n in reversed(sorted(names))]  # deliberately not sorted ascending


class FakeGcsClient:
    def __init__(self, bucket_names: list[str]) -> None:
        self.io: list[tuple[Any, ...]] = []
        self.buckets = {name: FakeBucket(self, name) for name in bucket_names}
        self.bucket_lookups: list[str] = []

    def bucket(self, name: str, *args: Any, **kwargs: Any) -> FakeBucket:
        self.bucket_lookups.append(name)
        if name not in self.buckets:
            raise AssertionError(f"fake GCS: bucket {name!r} was never configured")
        return self.buckets[name]

    def get_bucket(self, name: Any, *args: Any, **kwargs: Any) -> FakeBucket:
        return self.bucket(name if isinstance(name, str) else name.name)

    def lookup_bucket(self, name: str, *args: Any, **kwargs: Any) -> FakeBucket:
        return self.bucket(name)

    def list_blobs(self, bucket_or_name: Any, prefix: str | None = None, **kwargs: Any) -> list[FakeBlob]:
        name = bucket_or_name if isinstance(bucket_or_name, str) else bucket_or_name.name
        return self.bucket(name).list_blobs(prefix=prefix, **kwargs)


# ------------------------------------------------------------------ the journal


class LogCapture:
    def __init__(self, capsys: Any) -> None:
        self.buffer = io.StringIO()
        self.capsys = capsys
        self.printed: str = ""

    def text(self) -> str:
        out = self.capsys.readouterr().out
        self.printed += out
        return self.buffer.getvalue() + self.printed

    def events(self, event: str) -> list[dict[str, Any]]:
        found = []
        for line in self.text().splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            if isinstance(obj, dict) and obj.get("event") == event:
                found.append(obj)
        return found


def install_log_capture(monkeypatch: Any, capsys: Any) -> LogCapture:
    from thinkhow.platform import log

    cap = LogCapture(capsys)
    monkeypatch.setattr(log.log_event, "__defaults__", (cap.buffer,))
    return cap
