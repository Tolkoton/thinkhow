"""The scripted answers of local mode for the learning Job: the analyzer, the synthesizer and the
person-details check, told apart by the name of the schema."""

import json
from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel

from thinkhow.platform.llm import Turn

FINDING = "(локальний режим) Людина назвала план; фасилітатор поставив одне питання."
NOTE = "(локальний режим) Коли людина називає план, одне питання про перший крок тримає розмову."


def local_script(system: str, contents: Sequence[Turn], schema: type[BaseModel]) -> str:
    shape = schema.model_json_schema()
    if schema.__name__ == "SynthesisAnswer":
        return json.dumps(_synthesis(shape), ensure_ascii=False)
    if schema.__name__ == "VetAnswer":
        return json.dumps({"ok": True, "reason": ""})
    first = shape["$defs"]["ObservationAnswerItem"]["properties"]["anchor"]["enum"][0]
    one = {"kind": "progress", "finding": FINDING, "worked": True, "cause": "facilitation", "anchor": first}
    return json.dumps({"observations": [one]}, ensure_ascii=False)


def _synthesis(shape: dict[str, Any]) -> dict[str, Any]:
    """One facilitator note to the first card, citing the first observation."""
    upsert = shape["$defs"]["SynthesisUpsert"]["properties"]
    card = _first(upsert["cards"]["items"])
    cited = _first(upsert["observations"]["items"])
    note = {
        "id": f"{card}-local",
        "audience": "facilitator",
        "cards": [card],
        "title": "Локальна нотатка",
        "noticed": NOTE,
        "do": "Спитай, який перший крок людина зробить.",
        "observations": [cited],
    }
    return {"what": "локальна нотатка", "why": f"локальний режим ({cited})", "upsert": [note], "remove": []}


def _first(values: dict[str, Any]) -> str:
    """The first value of an `enum`; pydantic writes `const` for a one-value Literal."""
    return str(values["enum"][0] if "enum" in values else values["const"])
