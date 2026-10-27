"""The scripted analyzer of local mode: one fixed observation anchored to the first turn of the schema."""

import json
from collections.abc import Sequence

from pydantic import BaseModel

from thinkhow.platform.llm import Turn

FINDING = "(локальний режим) Людина назвала план; фасилітатор поставив одне питання."


def local_script(system: str, contents: Sequence[Turn], schema: type[BaseModel]) -> str:
    item = schema.model_json_schema()["$defs"]["ObservationAnswerItem"]
    first = item["properties"]["anchor"]["enum"][0]
    one = {"kind": "progress", "finding": FINDING, "worked": True, "cause": "facilitation", "anchor": first}
    return json.dumps({"observations": [one]}, ensure_ascii=False)
