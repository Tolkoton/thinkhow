"""The scripted model of local mode: a fixed facilitator answer in the shape of the asked schema.

`reply` comes first, so local mode streams like Vertex does (S1 Q2a).
"""

import json
import re
from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel

from thinkhow.platform.llm import Turn

REPLY = "(локальний режим) Уявіть, що план провалився. Що сталося першим?"
FRAME = re.compile(r"\[Репліка людини #(\d+)\]\n(.*)\Z", re.S)


def local_script(system: str, contents: Sequence[Turn], schema: type[BaseModel]) -> str:
    """Flow: the turn number and text from the frame → the first phase of the schema → the answer JSON."""
    turn_no, text = _frame(contents)
    answer: dict[str, Any] = {"reply": REPLY} if "reply" in schema.model_fields else {}
    answer["current_phase_id"] = _first_phase(schema)
    answer["phase_exit_met"] = False
    answer["map_updates"] = [
        {"op": "add", "id": f"i{turn_no}", "type": "plan", "text": text, "turn": f"t{turn_no}"}
    ]
    return json.dumps(answer, ensure_ascii=False)


def _frame(contents: Sequence[Turn]) -> tuple[int, str]:
    for turn in reversed(contents):
        if turn.role == "user" and (m := FRAME.search(turn.text)):
            return int(m.group(1)), m.group(2)
    return 0, ""


def _first_phase(schema: type[BaseModel]) -> str:
    phase = schema.model_json_schema()["properties"]["current_phase_id"]
    values = phase.get("enum") or [phase.get("const", "")]
    return str(values[0])
