"""The scripted analyzer of local mode: a fixed observation anchored to the first turn of the schema."""

import json
from collections.abc import Sequence

from pydantic import BaseModel

from thinkhow.platform.llm import Turn

FINDING = "(локальний режим) Людина назвала план; фасилітатор поставив одне питання."


def local_script(system: str, contents: Sequence[Turn], schema: type[BaseModel]) -> str:
    first = schema.model_json_schema()["properties"]["anchor"]["enum"][0]
    answer = {"finding": FINDING, "worked": True, "cause": "facilitation", "anchor": first}
    return json.dumps(answer, ensure_ascii=False)
