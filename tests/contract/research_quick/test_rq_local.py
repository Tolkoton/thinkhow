"""Contract tests of research-quick, the local twin (`web/local.py`): `local_found` and the `fact` item of
`local_script` (slice tester; from the contract)."""

import json
from typing import Any

from rq_fakes import PREMORTEM

from thinkhow.facilitation.respond import answer_schema, update_schema
from thinkhow.platform.llm import Found, Source, Turn
from thinkhow.web.local import local_found, local_script

LOCAL_SOURCE = Source("example.org", "https://example.org/local-search")


def contents(text: str, no: int = 3) -> list[Turn]:
    return [
        Turn("user", "Раніше"),
        Turn("model", "Розкажіть більше."),
        Turn(
            "user",
            f'[Карта проблеми зараз]\n{{"items":[],"phase_id":null,"last_turn":{no - 1}}}\n\n'
            f"[Репліка людини #{no}]\n{text}",
        ),
    ]


def test_local_found_gives_the_fixed_found_on_skilky_koshtuie_when_the_schema_has_reply() -> None:
    schema = answer_schema(PREMORTEM)
    texts = ("Не знаю, скільки коштує оренда офісу", "СКІЛЬКИ КОШТУЄ кава?", "А Скільки Коштує це?")
    for text in texts:
        assert local_found("system", contents(text), schema) == Found((text,), (LOCAL_SOURCE,), None), text
    no_reply = update_schema(PREMORTEM)
    assert local_found("system", contents("Не знаю, скільки коштує оренда."), no_reply) is None
    assert local_found("system", contents("Відкрию кав'ярню біля університету."), schema) is None


def without_text(obj: dict[str, Any]) -> list[dict[str, Any]]:
    return [{k: v for k, v in u.items() if k != "text"} for u in obj["map_updates"]]


def test_local_script_adds_a_fact_item_instead_of_a_plan_on_such_a_turn() -> None:
    schema = answer_schema(PREMORTEM)
    obj = json.loads(local_script("system", contents("Не знаю, скільки коштує оренда офісу."), schema))
    assert without_text(obj) == [{"op": "add", "id": "i3", "type": "fact", "turn": "t3"}]
    schema.model_validate_json(json.dumps(obj, ensure_ascii=False))
    plain = json.loads(local_script("system", contents("Відкрию кав'ярню біля університету."), schema))
    assert without_text(plain) == [{"op": "add", "id": "i3", "type": "plan", "turn": "t3"}]
