"""Helpers for the walking-skeleton block (integration) tests. Slice tester; from the feature artifact.

- RecordingStorage: the S1 `Storage` protocol and nothing more (four methods) over a `LocalStorage`;
  records every call as (method, bucket, path).
- RecordingLlm: an `Llm` that records every call and forwards to a scripted double, or raises
  `LlmUnavailable` on the calls planned to fail.
- FakeFacilitate: a `Facilitate` written by hand: records each `FacilitationContext`, streams two
  deltas and a valid `FacilitatorUpdate` with one `add` to the map.
- sse_events: the SSE body of S5 as a list of (event, data).
"""

from __future__ import annotations

import builtins
import json
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from thinkhow.facilitation.types import (
    FacilitationContext,
    FacilitatorUpdate,
    MapUpdate,
    ReplyDelta,
)
from thinkhow.platform.llm import Done, KnowledgeRev, LlmUnavailable, Turn
from thinkhow.platform.llm import ReplyDelta as LlmDelta
from thinkhow.platform.storage import Bucket, LocalStorage

REPO = Path(__file__).resolve().parents[3]
CARDS = REPO / "cards"
NOW = datetime(2026, 10, 22, 12, 0, 0, tzinfo=UTC)

OWNER_EMAIL = "owner@localhost"


def local_environ(folder: Path) -> dict[str, str]:
    return {
        "THINKHOW_LOCAL": "true",
        "THINKHOW_LOCAL_DIR": str(folder),
        "THINKHOW_OWNER_EMAIL": OWNER_EMAIL,
    }


@dataclass
class RecordingStorage:
    root: Path
    calls: builtins.list[tuple[str, str, str]] = field(default_factory=builtins.list)

    def __post_init__(self) -> None:
        self._inner = LocalStorage(self.root)

    def read(self, bucket: Bucket, path: str) -> bytes | None:
        self.calls.append(("read", bucket, path))
        return self._inner.read(bucket, path)

    def write(self, bucket: Bucket, path: str, data: bytes, content_type: str) -> None:
        self.calls.append(("write", bucket, path))
        self._inner.write(bucket, path, data, content_type)

    def create_if_absent(self, bucket: Bucket, path: str, data: bytes, content_type: str) -> bool:
        self.calls.append(("create_if_absent", bucket, path))
        return self._inner.create_if_absent(bucket, path, data, content_type)

    def list(self, bucket: Bucket, prefix: str) -> list[str]:
        self.calls.append(("list", bucket, prefix))
        return self._inner.list(bucket, prefix)

    def writes(self) -> builtins.list[tuple[str, str, str]]:
        return [c for c in self.calls if c[0] in ("write", "create_if_absent")]


@dataclass
class RecordingLlm:
    inner: Any
    fail_streams: int = 0
    stream_calls: list[dict[str, Any]] = field(default_factory=list)
    generate_calls: list[dict[str, Any]] = field(default_factory=list)

    def stream_json(
        self, system: str, contents: Sequence[Turn], schema: type[BaseModel], rev: KnowledgeRev | None
    ) -> Iterator[LlmDelta | Done]:
        self.stream_calls.append({"system": system, "contents": list(contents), "schema": schema, "rev": rev})
        if self.fail_streams > 0:
            self.fail_streams -= 1
            raise LlmUnavailable("planned")
        yield from self.inner.stream_json(system, contents, schema, rev)

    def generate_json(
        self, system: str, contents: Sequence[Turn], schema: type[Any], rev: KnowledgeRev | None
    ) -> Any:
        self.generate_calls.append(
            {"system": system, "contents": list(contents), "schema": schema, "rev": rev}
        )
        return self.inner.generate_json(system, contents, schema, rev)


@dataclass
class FakeFacilitate:
    contexts: list[FacilitationContext] = field(default_factory=list)

    def __call__(self, ctx: FacilitationContext) -> Iterator[ReplyDelta | FacilitatorUpdate]:
        self.contexts.append(ctx)
        yield ReplyDelta("Що ")
        yield ReplyDelta("далі?")
        yield FacilitatorUpdate(
            reply="Що далі?",
            current_phase_id="p1",
            phase_exit_met=False,
            map_updates=[
                MapUpdate(op="add", id=f"i{ctx.turn_no}", type="plan", text=ctx.text, turn=f"t{ctx.turn_no}")
            ],
        )


def sse_events(body: str) -> list[tuple[str, dict[str, Any]]]:
    events = []
    for block in body.strip().split("\n\n"):
        lines = block.split("\n")
        name = next(x for x in lines if x.startswith("event:")).split(":", 1)[1].strip()
        data = next(x for x in lines if x.startswith("data:")).split(":", 1)[1].strip()
        events.append((name, json.loads(data)))
    return events
