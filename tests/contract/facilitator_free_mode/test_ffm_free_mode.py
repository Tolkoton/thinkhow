"""Contract tests of facilitator-free-mode: the null phase of the update and local mode (slice tester)."""

import json

from ffm_fakes import ALPHA, SOLO

from thinkhow.facilitation import FacilitatorUpdate
from thinkhow.facilitation.respond import answer_schema, update_schema
from thinkhow.platform.llm import Turn
from thinkhow.web.local import local_script


def test_facilitator_update_takes_null_as_the_free_mode_phase() -> None:
    update = FacilitatorUpdate(
        reply="Яка ваша ціль?", current_phase_id=None, phase_exit_met=False, map_updates=[]
    )
    assert update.current_phase_id is None


def test_local_mode_answers_the_first_phase_for_one_and_many_phases() -> None:
    contents = [
        Turn("user", "Раніше"),
        Turn("model", "Розкажіть більше."),
        Turn(
            "user",
            '[Карта проблеми зараз]\n{"items":[],"phase_id":null,"last_turn":2}\n\n'
            "[Стан] Вільний режим уже триває: людина чула, що картка не підходить. Не кажи цього знову.\n\n"
            "[Репліка людини #3]\nХочу заробити більше.",
        ),
    ]
    for card, first in ((ALPHA, "a_one"), (SOLO, "s_only")):
        for schema in (answer_schema(card), update_schema(card)):
            raw = local_script("system", contents, schema)
            assert json.loads(raw)["current_phase_id"] == first, (card.id, schema)
            schema.model_validate_json(raw)


def test_one_phase_card_sends_an_enum_not_a_const() -> None:
    """Task 704: pydantic writes `const` for a one-value Literal; Vertex gets the verified `enum`."""
    for card, ids in ((SOLO, ["s_only"]), (ALPHA, ["a_one", "a_two", "a_three"])):
        for schema in (answer_schema(card), update_schema(card)):
            phase = schema.model_json_schema()["properties"]["current_phase_id"]
            assert phase["anyOf"] == [{"type": "string", "enum": ids}, {"type": "null"}], (card.id, phase)
            assert schema.model_validate({**_update_fields(schema), "current_phase_id": ids[0]})
            assert schema.model_validate({**_update_fields(schema), "current_phase_id": None})


def _update_fields(schema: type) -> dict[str, object]:
    base: dict[str, object] = {"phase_exit_met": False, "map_updates": []}
    return {"reply": "Так?", **base} if "reply" in schema.model_fields else base
