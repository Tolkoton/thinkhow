"""Contract test of the local twin of the router (`web/local.py`) (slice tester; from the contract)."""

import json

from rt_cards import ALPHA, PREMORTEM
from rt_fakes import knowledge

from thinkhow.facilitation.route import router_schema
from thinkhow.platform.llm import Turn
from thinkhow.web.local import local_script

UNCLEAR = {
    "intent": "unclear",
    "structuredness": "unclear",
    "reversibility": "unclear",
    "stakes": "unclear",
    "data": "unclear",
    "options": "unclear",
    "emotion": "unclear",
    "social": "unclear",
}


def test_local_twin_answers_the_router_schema_with_choose_pre_mortem_all_unclear_and_no_reply() -> None:
    schema = router_schema(knowledge((ALPHA, PREMORTEM), rev=1, n=0))
    contents = [
        Turn(
            "user",
            "[Стан вибору способу]\n\n"
            '[Карта проблеми зараз]\n{"items":[],"phase_id":null,"last_turn":0}\n\n'
            "[Репліка людини #1]\nХочу відкрити кав'ярню.",
        )
    ]
    raw = local_script("system", contents, schema)
    doc = json.loads(raw)
    assert doc["action"] == "choose"
    assert doc["card_id"] == "pre-mortem"
    assert doc["profile"] == UNCLEAR
    assert doc["reply"] is None
    schema.model_validate_json(raw)
