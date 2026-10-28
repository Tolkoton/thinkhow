"""Builder test of task 704 (not the sealed contract): a one-phase card's schema carries an `enum`."""

from ffm_fakes import ALPHA, SOLO

from thinkhow.facilitation.respond import answer_schema, update_schema


def test_one_phase_card_sends_an_enum_not_a_const() -> None:
    """pydantic writes `const` for a one-value Literal; Vertex gets the verified `enum`."""
    for card, ids in ((SOLO, ["s_only"]), (ALPHA, ["a_one", "a_two", "a_three"])):
        for schema in (answer_schema(card), update_schema(card)):
            phase = schema.model_json_schema()["properties"]["current_phase_id"]
            assert phase["anyOf"] == [{"type": "string", "enum": ids}, {"type": "null"}], (card.id, phase)
            assert schema.model_validate({**_update_fields(schema), "current_phase_id": ids[0]})
            assert schema.model_validate({**_update_fields(schema), "current_phase_id": None})


def _update_fields(schema: type) -> dict[str, object]:
    base: dict[str, object] = {"phase_exit_met": False, "map_updates": []}
    return {"reply": "Так?", **base} if "reply" in schema.model_fields else base
