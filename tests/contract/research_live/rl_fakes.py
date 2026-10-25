"""Hand-written inputs for the contract tests of research-live (slice tester; from the contract)."""

import importlib.util
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType
from typing import Any, Literal

from thinkhow.facilitation.types import MapItem
from thinkhow.workspace import conversation as conv_file

LIVE = Path(__file__).resolve().parents[2] / "live" / "test_research_owner_live.py"


def live_module() -> ModuleType:
    """The live test module, loaded by path under its own name (tests have no packages)."""
    spec = importlib.util.spec_from_file_location("rl_owner_live_under_test", LIVE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


T0 = datetime(2026, 10, 20, 9, 0, tzinfo=UTC)


def turn(no: int, role: Literal["user", "model"], text: str = "") -> conv_file.Turn:
    return conv_file.Turn(no=no, role=role, at=T0 + timedelta(minutes=no), text=text or f"репліка {no}")


def owner_conversation() -> conv_file.Conversation:
    """One session #1–#30: the person on odd numbers, the model on even (as the owner's topic)."""
    turns = [turn(n, "user" if n % 2 else "model") for n in range(1, 31)]
    return conv_file.Conversation(title="Машина", sessions=[conv_file.SessionDoc(no=1, turns=turns)])


def item(item_id: str, turn_ref: str, kind: Any = "goal") -> MapItem:
    return MapItem(id=item_id, type=kind, text=f"пункт {item_id}", turn=turn_ref)


def decision(turn_no: int, kind: str = "choose", card: str | None = "weighted-matrix") -> dict[str, Any]:
    return {
        "turn": turn_no,
        "rev": {"rev": "r1", "n": 12},
        "kind": kind,
        "profile": None,
        "candidates": [],
        "card_id": card,
        "end": None,
        "why": f"рішення на репліку {turn_no}",
    }


def research(turn_no: int, depth: str = "quick", query: str = "ціна Škoda Octavia 2026") -> dict[str, Any]:
    return {
        "turn": turn_no,
        "depth": depth,
        "queries": [query],
        "sources": [{"title": "Джерело", "url": f"https://example.org/{turn_no}"}],
        "suggestions_html": None,
        "question": None,
        "report": None,
    }


def llm_call(prompt_tokens: int, queries: int = 0) -> dict[str, Any]:
    return {
        "severity": "INFO",
        "model": "gemini-2.5-pro",
        "prompt_tokens": prompt_tokens,
        "output_tokens": 300,
        "thought_tokens": 100,
        "latency_ms": 2100,
        "attempts": 1,
        "rev": "r1",
        "n": 12,
        "outcome": "ok",
        "search": queries > 0,
        "queries": queries,
        "event": "llm_call",
        "request_id": None,
    }


def log_lines(*lines: dict[str, Any]) -> str:
    return "".join(json.dumps(line, ensure_ascii=False) + "\n" for line in lines)
