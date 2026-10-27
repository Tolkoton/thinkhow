"""Helpers for the catch-up tests of `scripts/analyze_owner_conversation.py` (slice analysis-rules, Seam 4).

Slice tester; built from the contract and the script's public names (`main`, `before_turns`, `topic_folder`,
`make_llm`), not from its bodies.

- `load_script()` imports the script as a module (run as `python scripts/analyze_owner_conversation.py`).
- `PlanLlm` answers the new analyzer (schema with `observations`) with planned observations and the old
  analyzer (schema `finding, worked, cause, anchor`, commit c14fd9b) with one observation; records every call.
- `guard_artifact` keeps the owner's real artifact byte for byte: whatever a test run writes there is undone.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "scripts" / "analyze_owner_conversation.py"
ARTIFACT = REPO / ".engine" / "artifacts" / "analysis-rules" / "owner-t-84d1517cb1c1.md"
OLD_COMMIT = "c14fd9b"
OPP_TITLE = "Дерево можливостей, найризикованіше припущення і пріоритети"  # cards/opportunity-tree.yaml

# (anchor number, kind, cause, worked) — passes the exit check: stuck on 5, 11, 15; none on 9, 13.
PASSING: list[tuple[int, str, str, bool]] = [
    (5, "stuck", "facilitation", False),
    (9, "progress", "router", True),
    (11, "stuck", "method", False),
    (13, "method_fit", "facilitation", True),
    (15, "stuck", "circumstances", False),
]


def load_script() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("analyze_owner_conversation_under_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _resolve(js: dict[str, Any], node: dict[str, Any]) -> dict[str, Any]:
    while "$ref" in node:
        node = js["$defs"][node["$ref"].rsplit("/", 1)[-1]]
    return node


def is_new_schema(schema: type[BaseModel]) -> bool:
    return "observations" in schema.model_json_schema().get("properties", {})


def anchors_of(schema: type[BaseModel]) -> list[str]:
    js = schema.model_json_schema()
    if is_new_schema(schema):
        items = _resolve(js, _resolve(js, js["properties"]["observations"])["items"])
        return list(_resolve(js, items["properties"]["anchor"])["enum"])
    return list(_resolve(js, js["properties"]["anchor"])["enum"])


def finding_of(marker: str, n: int, kind: str) -> str:
    return f"{marker}-{kind}-t{n}"


@dataclass
class Call:
    system: str
    contents: list[Any]
    schema: type[BaseModel]

    @property
    def new(self) -> bool:
        return is_new_schema(self.schema)

    def lines(self) -> list[str]:
        text = "\n".join(t.text for t in self.contents)
        return [line for line in text.split("\n") if line.strip()]

    def turn_lines(self) -> list[str]:
        return [line for line in self.lines() if line.startswith("#")]


@dataclass
class PlanLlm:
    plan: Sequence[tuple[int, str, str, bool]] = tuple(PASSING)
    marker: str = "НОВИЙ"
    old_marker: str = "СТАРИЙ"
    calls: list[Call] = field(default_factory=list)

    def stream_json(self, *args: Any, **kwargs: Any) -> Any:
        raise AssertionError("the analyzers use generate_json")

    def search_text(self, *args: Any, **kwargs: Any) -> Any:
        raise AssertionError("the analyzers do not search")

    def generate_json(self, system: str, contents: Sequence[Any], schema: Any, rev: Any) -> Any:
        self.calls.append(Call(system, list(contents), schema))
        if is_new_schema(schema):
            return schema.model_validate(
                {
                    "observations": [
                        {
                            "kind": kind,
                            "finding": finding_of(self.marker, n, kind),
                            "worked": worked,
                            "cause": cause,
                            "anchor": f"t{n}",
                        }
                        for n, kind, cause, worked in self.plan
                    ]
                }
            )
        return schema.model_validate(
            {"finding": f"{self.old_marker}-одне", "worked": False, "cause": "facilitation", "anchor": "t15"}
        )


@pytest.fixture
def guard_artifact() -> Iterator[None]:
    before = ARTIFACT.read_bytes() if ARTIFACT.exists() else None
    try:
        yield
    finally:
        if before is None:
            ARTIFACT.unlink(missing_ok=True)
        else:
            ARTIFACT.write_bytes(before)


def run_main(monkeypatch: pytest.MonkeyPatch, llm: PlanLlm, attempt: int | None = None) -> tuple[int, str]:
    """The script's `main` with the fake model in place of Vertex; returns (exit code, the artifact text)."""
    module = load_script()
    monkeypatch.setattr(module, "make_llm", lambda *a, **k: llm)
    for key, value in {
        "THINKHOW_MODEL": "gemini-4-argon",
        "THINKHOW_LOCATION": "eu",
        "THINKHOW_USERS_BUCKET": "test-users",
        "THINKHOW_SYSTEM_BUCKET": "test-system",
        "THINKHOW_OWNER_EMAIL": "owner@example.com",
    }.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("THINKHOW_LOCAL", raising=False)
    argv = [str(SCRIPT)] + ([] if attempt is None else ["--attempt", str(attempt)])
    monkeypatch.setattr(sys, "argv", argv)
    try:
        code = module.main()
    except SystemExit as stop:
        code = stop.code
    text = ARTIFACT.read_text(encoding="utf-8") if ARTIFACT.exists() else ""
    return int(code or 0), text
