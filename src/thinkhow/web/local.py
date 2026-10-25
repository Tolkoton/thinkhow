"""The scripted model of local mode: a fixed facilitator answer in the shape of the asked schema.

`reply` comes first, so local mode streams like Vertex does (S1 Q2a).
"""

import json
import re
from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel

from thinkhow.platform.llm import Found, Source, Turn

REPLY = "(локальний режим) Уявіть, що план провалився. Що сталося першим?"
UNCLEAR = ("intent", "structuredness", "reversibility", "stakes", "data", "options", "emotion", "social")
ROUTER_CHOICE: dict[str, Any] = {
    "action": "choose",
    "profile": dict.fromkeys(UNCLEAR, "unclear"),
    "candidates": [],
    "card_id": "pre-mortem",
    "reply": None,
    "why": "(локальний режим) одразу Pre-mortem",
}
ASKS_PRICE = "скільки коштує"
LOCAL_SOURCE = Source("example.org", "https://example.org/local-search")
FRAME = re.compile(r"\[Репліка людини #(\d+)\]\n(.*)\Z", re.S)


def local_script(system: str, contents: Sequence[Turn], schema: type[BaseModel]) -> str:
    """Flow: router schema → choose pre-mortem; else the frame's turn and text → first phase → JSON."""
    if "action" in schema.model_fields:
        return json.dumps(ROUTER_CHOICE, ensure_ascii=False)
    turn_no, text = _frame(contents)
    answer: dict[str, Any] = {"reply": REPLY} if "reply" in schema.model_fields else {}
    answer["current_phase_id"] = _first_phase(schema)
    answer["phase_exit_met"] = False
    answer["map_updates"] = [
        {"op": "add", "id": f"i{turn_no}", "type": _item_type(text), "text": text, "turn": f"t{turn_no}"}
    ]
    return json.dumps(answer, ensure_ascii=False)


def _frame(contents: Sequence[Turn]) -> tuple[int, str]:
    for turn in reversed(contents):
        if turn.role == "user" and (m := FRAME.search(turn.text)):
            return int(m.group(1)), m.group(2)
    return 0, ""


def _first_phase(schema: type[BaseModel]) -> str:
    """The card's first phase: from `enum` or `const`, also inside `anyOf` with null (free mode)."""
    phase = schema.model_json_schema()["properties"]["current_phase_id"]
    branch = next((b for b in phase.get("anyOf", [phase]) if b.get("type") != "null"), phase)
    values = branch.get("enum") or [branch.get("const", "")]
    return str(values[0])


def local_search(system: str, prompt: str) -> tuple[str, Found | None]:
    """The local double's web search of the deep cycle: a fixed text and source."""
    return f"(локально) знайдено: {prompt}", Found(
        queries=(prompt[:80],), sources=(LOCAL_SOURCE,), suggestions_html=None
    )


def local_found(system: str, contents: Sequence[Turn], schema: type[BaseModel]) -> Found | None:
    """The local double's search: a fixed «found» when the person's turn asks «скільки коштує»."""
    _, text = _frame(contents)
    if "reply" not in schema.model_fields or not _asks_price(text):
        return None
    return Found(queries=(text[:80],), sources=(LOCAL_SOURCE,), suggestions_html=None)


def _asks_price(text: str) -> bool:
    return ASKS_PRICE in text.lower()


def _item_type(text: str) -> str:
    """A turn that asks a price is answered by a fact; any other one is the person's plan."""
    return "fact" if _asks_price(text) else "plan"
