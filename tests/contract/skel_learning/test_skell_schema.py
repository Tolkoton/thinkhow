"""Contract tests of skel-learning: answer_schema, ANALYZER, local_script (slice tester).

Carried over by objection (task 720, answer A) to analysis-rules, Seam «Схема відповіді»:
`{observations: list[{kind, finding, worked, cause, anchor}]}`, `min_length=1`, no upper bound, four causes,
the model's `kind` with `step` (S6 step-results: «`kind` схеми відповіді аналізатора отримує `"step"`»);
`local_script` answers one `progress` observation on the first value of the enum.
"""

import json
import re

import pytest
from pydantic import ValidationError
from skell_fakes import item_properties

from thinkhow.learning.analyze import ANALYZER, answer_schema
from thinkhow.learning.local import local_script
from thinkhow.platform.llm import Turn

VALID = {"finding": "Фасилітатор поставив одне питання.", "worked": True, "cause": "facilitation"}


def item(anchor: str, kind: str = "method_fit", **change: object) -> dict[str, object]:
    return {"kind": kind, **VALID, "anchor": anchor, **change}


def test_answer_schema_fields_in_order_and_anchor_is_a_string_enum_of_the_turns() -> None:
    schema = answer_schema([3, 4])
    assert list(schema.model_fields) == ["observations"]
    props = item_properties(schema)
    assert list(props) == ["kind", "finding", "worked", "cause", "anchor"]
    anchor = props["anchor"]
    assert anchor["type"] == "string"
    assert anchor["enum"] == ["t3", "t4"]
    assert "const" not in anchor


def test_answer_schema_of_one_turn_is_still_an_enum_not_const() -> None:
    anchor = item_properties(answer_schema([5]))["anchor"]
    assert anchor["type"] == "string"
    assert anchor["enum"] == ["t5"]
    assert "const" not in anchor


def test_answer_schema_accepts_a_valid_answer_and_refuses_bad_ones() -> None:
    schema = answer_schema([3, 4])
    ok = schema.model_validate({"observations": [item("t4")]})
    assert ok.model_dump() == {"observations": [item("t4")]}
    many = [item("t3", "progress"), item("t4", "stuck"), item("t3", "method_fit")] * 3  # no upper bound
    assert schema.model_validate({"observations": many}).model_dump() == {"observations": many}
    bad: object
    for bad in (
        {"observations": [item("t5")]},  # not a turn of this range
        {"observations": [item("t1")]},
        {"observations": [item("3")]},
        {"observations": [item("t3", finding="")]},  # finding must not be empty
        {"observations": [item("t3", cause="model")]},  # cause outside the four
        {"observations": [item("t3", kind="other")]},  # kind outside the four
        {"observations": [item("t3"), item("t5")]},  # one bad item spoils the answer
        {"observations": []},  # min_length=1
        {},
        item("t3"),  # the old shape: one observation, not a set
    ):
        with pytest.raises(ValidationError):
            schema.model_validate(bad)
    props = item_properties(schema)
    assert set(props["cause"]["enum"]) == {"router", "method", "facilitation", "circumstances"}
    assert set(props["kind"]["enum"]) == {"progress", "stuck", "method_fit", "step"}


def test_analyzer_is_a_ukrainian_system_instruction() -> None:
    assert ANALYZER.strip() != ""
    assert re.search(r"[А-Яа-яІіЇїЄєҐґ]{4,}", ANALYZER)


def test_local_script_answers_the_fixed_observation_anchored_to_the_first_enum_value() -> None:
    schema = answer_schema([7, 8])
    raw = local_script(ANALYZER, [Turn("user", "#7 людина: план\n#8 фасилітатор: питання")], schema)
    assert json.loads(raw) == {
        "observations": [
            {
                "kind": "progress",
                "finding": "(локальний режим) Людина назвала план; фасилітатор поставив одне питання.",
                "worked": True,
                "cause": "facilitation",
                "anchor": "t7",
            }
        ]
    }
    schema.model_validate_json(raw)
