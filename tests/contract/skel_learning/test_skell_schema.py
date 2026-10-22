"""Contract tests of skel-learning: answer_schema, ANALYZER, local_script (slice tester)."""

import json
import re

import pytest
from pydantic import ValidationError

from thinkhow.learning.analyze import ANALYZER, answer_schema
from thinkhow.learning.local import local_script
from thinkhow.platform.llm import Turn

VALID = {"finding": "Фасилітатор поставив одне питання.", "worked": True, "cause": "facilitation"}


def test_answer_schema_fields_in_order_and_anchor_is_a_string_enum_of_the_turns() -> None:
    schema = answer_schema([3, 4])
    assert list(schema.model_fields) == ["finding", "worked", "cause", "anchor"]
    anchor = schema.model_json_schema()["properties"]["anchor"]
    assert anchor["type"] == "string"
    assert anchor["enum"] == ["t3", "t4"]
    assert "const" not in anchor


def test_answer_schema_of_one_turn_is_still_an_enum_not_const() -> None:
    anchor = answer_schema([5]).model_json_schema()["properties"]["anchor"]
    assert anchor["type"] == "string"
    assert anchor["enum"] == ["t5"]
    assert "const" not in anchor


def test_answer_schema_accepts_a_valid_answer_and_refuses_bad_ones() -> None:
    schema = answer_schema([3, 4])
    ok = schema.model_validate({**VALID, "anchor": "t4"})
    assert ok.model_dump() == {**VALID, "anchor": "t4"}
    for bad in (
        {**VALID, "anchor": "t5"},  # not a turn of this session
        {**VALID, "anchor": "t1"},
        {**VALID, "anchor": "3"},
        {**VALID, "finding": "", "anchor": "t3"},  # finding must not be empty
        {**VALID, "cause": "model", "anchor": "t3"},  # cause outside the three
    ):
        with pytest.raises(ValidationError):
            schema.model_validate(bad)
    cause = schema.model_json_schema()["properties"]["cause"]
    assert set(cause["enum"]) == {"method", "facilitation", "circumstances"}


def test_analyzer_is_a_ukrainian_system_instruction() -> None:
    assert ANALYZER.strip() != ""
    assert re.search(r"[А-Яа-яІіЇїЄєҐґ]{4,}", ANALYZER)


def test_local_script_answers_the_fixed_observation_anchored_to_the_first_enum_value() -> None:
    schema = answer_schema([7, 8])
    raw = local_script(ANALYZER, [Turn("user", "#7 людина: план\n#8 фасилітатор: питання")], schema)
    assert json.loads(raw) == {
        "finding": "(локальний режим) Людина назвала план; фасилітатор поставив одне питання.",
        "worked": True,
        "cause": "facilitation",
        "anchor": "t7",
    }
    schema.model_validate_json(raw)
