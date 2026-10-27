"""Contract tests of knowledge-versions: learning.vet, vet_with and measure (slice tester)."""

from collections.abc import Sequence
from typing import Any

import pytest
from kv_fakes import card_dict, rec
from pydantic import BaseModel, ValidationError

from thinkhow.facilitation.respond import system_instruction
from thinkhow.facilitation.route import router_instruction
from thinkhow.knowledge import Card, CurrentKnowledge
from thinkhow.learning.vet import measure, vet_with
from thinkhow.platform.llm import LlmUnavailable, ScriptedLlm, Turn


def scripted(answer: str) -> ScriptedLlm:
    return ScriptedLlm(lambda system, contents, schema: answer)


def seen_text(llm: ScriptedLlm) -> str:
    system, contents, _ = llm.calls[0]
    return system + "\n".join(turn.text for turn in contents)


def test_vet_with_asks_the_model_once_with_an_ok_reason_schema_over_the_records_text() -> None:
    llm = scripted('{"ok": true, "reason": ""}')
    records = [rec("m1", "помічено-перше"), rec("m2", "помічено-друге")]
    assert vet_with(llm)(records) is None
    assert len(llm.calls) == 1
    schema: type[BaseModel] = llm.calls[0][2]
    assert set(schema.model_fields) == {"ok", "reason"}
    text = seen_text(llm)
    assert "помічено-перше" in text and "помічено-друге" in text


def test_vet_with_returns_the_reason_when_the_model_says_not_ok() -> None:
    llm = scripted('{"ok": false, "reason": "названо Олену зі Львова"}')
    assert vet_with(llm)([rec("m1", "Олена зі Львова втратила 3000 €")]) == "названо Олену зі Львова"


def test_vet_with_lets_the_model_errors_through() -> None:
    def down(system: str, contents: Sequence[Turn], schema: type[BaseModel]) -> str:
        raise LlmUnavailable("no answer")

    with pytest.raises(LlmUnavailable):
        vet_with(ScriptedLlm(down))([rec("m1")])
    with pytest.raises(ValidationError):
        vet_with(scripted('{"verdict": "так"}'))([rec("m1")])


def card(cid: str, **patch: Any) -> Card:
    data = card_dict(cid)
    for half, fields in patch.items():
        data[half].update(fields)
    return Card.model_validate(data)


def knowledge_of(cards: list[Card], memory: list[Any]) -> CurrentKnowledge:
    return CurrentKnowledge(rev=3, n=0, cards={c.id: c for c in cards}, memory=memory)


def test_measure_is_the_length_of_the_longest_reader_instruction() -> None:
    # a long facilitator half: the facilitator instruction of that card is the longest
    k = knowledge_of([card("alpha"), card("beta", facilitator={"purpose": "ф" * 40_000})], [rec("m1")])
    beta = len(system_instruction(k.cards["beta"], k.memory, None, True))
    assert beta > len(router_instruction(k, None))
    assert beta > len(system_instruction(k.cards["alpha"], k.memory, None, True))
    assert measure(k) == beta
    # long router halves on every card: the router instruction is the longest
    k = knowledge_of([card(c, router={"needs": "р" * 30_000}) for c in ("alpha", "beta", "gamma")], [])
    router = len(router_instruction(k, None))
    assert all(router > len(system_instruction(c, k.memory, None, True)) for c in k.cards.values())
    assert measure(k) == router
    # a long memory record of one card: the facilitator instruction of that card is the longest
    k = knowledge_of([card("alpha"), card("beta")], [rec("m1", "п" * 60_000, cards=["beta"]), rec("m2")])
    beta = len(system_instruction(k.cards["beta"], k.memory, None, True))
    assert beta > 60_000 > len(router_instruction(k, None))
    assert beta >= len(system_instruction(k.cards["alpha"], k.memory, None, True))
    assert measure(k) == beta
