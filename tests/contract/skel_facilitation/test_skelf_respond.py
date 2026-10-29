"""Contract tests of skel-facilitation: `respond` (slice tester; written from the contract, not the code)."""

import json

import pytest
from pydantic import ValidationError
from skelf_fakes import (
    ADD,
    ALPHA,
    HISTORY,
    MEMORY,
    PROBLEM_MAP,
    ScenarioLlm,
    answer,
    answer_reply_last,
    collect,
    context,
    knowledge,
    update_only,
)

from thinkhow.facilitation import FacilitationError, FacilitatorUpdate, ReplyDelta, respond
from thinkhow.knowledge import MemoryRecord, card_prompt
from thinkhow.platform import llm as pl

# The facilitator rules are not held verbatim here (owner's answer Б, task 724): the golden copies of other
# slices hold the text (`facilitator_free_mode/ffm_fakes.py`, `voice_reply_language/vrl_fakes.py`). This test
# keeps the contract's two replacements (Q5) and the order rules → card → memory.
NEW_ITEM_ID = "«i3»"
TURN_ANCHOR = "«t<номер з рамки репліки>»"

RETRY_ASK = "Поверни лише оновлення до своєї відповіді вище: фаза, вихід, зміни карти."
REPLY = "Уявіть: минув рік, і кав'ярня закрилася. Що сталося?"


def test_unknown_card_raises_value_error_before_any_model_call() -> None:
    fake = ScenarioLlm(deltas=["x"], done_raw=answer("x", "a_one"))
    items, exc = collect(lambda: respond(context(card_id="nope"), knowledge(), fake))
    assert isinstance(exc, ValueError)
    assert items == []
    assert fake.stream_calls == [] and fake.generate_calls == []


# A one-card record that names this card (alpha): it keeps the check of a one-card «Картки:» line
# now that M-2 (`cards: [gamma]`) is not in card alpha's instruction (notes-readers objection,
# owner's answer A, task 724).
OWN_ONE_CARD = MemoryRecord(
    id="M-3",
    title="Свій досвід",
    cards=["alpha"],
    noticed="людина пропускає фазу",
    do="назвати фазу ще раз",
    basis="2 сесії.",
)


def test_system_instruction_is_poc_rules_then_card_then_all_memory() -> None:
    # The name is kept for the ledger; since notes-readers Q1 the memory section holds only the
    # facilitator records whose `cards` name this card («розділ «# Пам'ять досвіду» містить лише
    # записи з `audience == "facilitator"` і `card.id in record.cards`»).
    fake = ScenarioLlm(deltas=[REPLY], done_raw=answer(REPLY, "a_one"))
    collect(lambda: respond(context(), knowledge(memory=[*MEMORY, OWN_ONE_CARD]), fake))
    system = fake.stream_calls[0].system
    item_id_at, anchor_at = system.find(NEW_ITEM_ID), system.find(TURN_ANCHOR)
    assert item_id_at != -1 and anchor_at != -1, "the rules lack the two replacements of Q5"
    card_head = system.find("# Картка")
    assert card_head > max(item_id_at, anchor_at), "the rules do not come before «# Картка»"
    card_at = system.find(card_prompt(ALPHA), card_head)
    assert card_at != -1
    memory_head = system.find("# Пам'ять досвіду", card_at + len(card_prompt(ALPHA)))
    assert memory_head != -1
    memory = system[memory_head:]
    lines = memory.splitlines()
    # every record that names card alpha (M-1, M-3) — in full; the one naming only gamma (M-2) — nowhere
    own = [MEMORY[0], OWN_ONE_CARD]
    assert [rec.id for rec in own] == ["M-1", "M-3"] and MEMORY[1].cards == ["gamma"]
    for rec in own:
        assert f"### {rec.id} — {rec.title}" in lines
        assert f"Що помітили: {rec.noticed}" in lines
        assert f"Що робити: {rec.do}" in lines
        assert f"Підстава: {rec.basis}" in lines
    foreign = MEMORY[1]
    assert foreign.id not in system and foreign.title not in system
    assert foreign.noticed not in system and foreign.do not in system
    cards_lines = [line for line in lines if line.startswith("Картки:")]
    assert len(cards_lines) == 2
    assert "alpha" in cards_lines[0] and "beta" in cards_lines[0]
    assert cards_lines[0].index("alpha") < cards_lines[0].index(",") < cards_lines[0].index("beta")
    assert "alpha" in cards_lines[1] and "," not in cards_lines[1]
    assert "gamma" not in memory
    assert "s2#" not in system and "«t3»" not in system


def test_empty_memory_is_written_as_still_empty() -> None:
    fake = ScenarioLlm(deltas=[REPLY], done_raw=answer(REPLY, "a_one"))
    collect(lambda: respond(context(), knowledge(memory=[]), fake))
    system = fake.stream_calls[0].system
    memory_head = system.find("# Пам'ять досвіду")
    assert memory_head != -1
    assert "(поки порожня)" in system[memory_head:]


def test_contents_are_history_as_llm_turns_plus_one_framed_current_turn() -> None:
    fake = ScenarioLlm(deltas=[REPLY], done_raw=answer(REPLY, "a_one"))
    collect(lambda: respond(context(turn_no=3, text="За пів року, біля університету."), knowledge(), fake))
    contents = fake.stream_calls[0].contents
    assert contents[:-1] == [
        pl.Turn(role="user", text="Хочу відкрити кав'ярню."),
        pl.Turn(role="model", text="Який у вас план і за який строк?"),
    ]
    assert len(contents) == len(HISTORY) + 1
    last = contents[-1]
    assert type(last) is pl.Turn and last.role == "user"
    head = "[Карта проблеми зараз]\n"
    tail = "\n\n[Репліка людини #3]\nЗа пів року, біля університету."
    assert last.text.startswith(head)
    assert last.text.endswith(tail)
    map_json = last.text[len(head) : len(last.text) - len(tail)]
    assert json.loads(map_json) == {
        "items": [{"id": "i1", "type": "plan", "text": "кав'ярня біля університету", "turn": "t1"}],
        "phase_id": "a_one",
        "last_turn": 1,
    }
    assert PROBLEM_MAP.phase_id == "a_one"


def test_stream_schema_has_reply_first_and_only_the_cards_phases() -> None:
    fake = ScenarioLlm(deltas=[REPLY], done_raw=answer(REPLY, "a_one"))
    collect(lambda: respond(context(card_id="alpha"), knowledge(), fake))
    schema = fake.stream_calls[0].schema
    assert list(schema.model_fields)[0] == "reply"
    assert set(schema.model_fields) == {"reply", "current_phase_id", "phase_exit_met", "map_updates"}
    for phase in ("a_one", "a_two", "a_three"):
        schema.model_validate_json(answer("Що сталося?", phase))
    for foreign in ("b_one", "phase_1_time_travel", ""):
        with pytest.raises(ValidationError):
            schema.model_validate_json(answer("Що сталося?", foreign))


def test_stream_call_carries_the_knowledge_rev_pair() -> None:
    fake = ScenarioLlm(deltas=[REPLY], done_raw=answer(REPLY, "a_one"))
    collect(lambda: respond(context(), knowledge(), fake))
    assert len(fake.stream_calls) == 1
    assert fake.stream_calls[0].rev == pl.KnowledgeRev(rev=3, n=7)


def test_valid_answer_with_deltas_passes_them_on_then_one_update() -> None:
    fake = ScenarioLlm(
        deltas=["Уявіть: минув рік, ", "і кав'ярня закрилася. ", "Що сталося?"],
        done_raw=answer(REPLY, "a_two", True, [ADD]),
    )
    items, exc = collect(lambda: respond(context(), knowledge(), fake))
    assert exc is None
    assert items[:3] == [
        ReplyDelta(text="Уявіть: минув рік, "),
        ReplyDelta(text="і кав'ярня закрилася. "),
        ReplyDelta(text="Що сталося?"),
    ]
    assert len(items) == 4
    update = items[3]
    assert type(update) is FacilitatorUpdate
    assert update.model_dump() == {
        "reply": REPLY,
        "current_phase_id": "a_two",
        "phase_exit_met": True,
        "map_updates": [ADD],
    }
    assert fake.generate_calls == []


def test_valid_answer_with_reply_not_first_yields_one_delta_then_update() -> None:
    fake = ScenarioLlm(deltas=[], done_raw=answer_reply_last(REPLY, "a_one"))
    items, exc = collect(lambda: respond(context(), knowledge(), fake))
    assert exc is None
    assert len(items) == 2
    assert items[0] == ReplyDelta(text=REPLY)
    assert type(items[1]) is FacilitatorUpdate
    assert items[1].reply == REPLY and items[1].current_phase_id == "a_one"
    assert fake.generate_calls == []


def test_invalid_update_after_shown_text_retries_only_the_update() -> None:
    shown = ["Уявіть провал. ", "Що сталося першим?"]
    fake = ScenarioLlm(
        deltas=list(shown),
        # the model named a phase of another card
        done_raw=answer("Уявіть провал. Що сталося першим?", "b_one"),
        generate=[update_only("a_three", False, [ADD])],
    )
    items, exc = collect(lambda: respond(context(), knowledge(), fake))
    assert exc is None
    assert items[:2] == [ReplyDelta(text="Уявіть провал. "), ReplyDelta(text="Що сталося першим?")]
    assert len(items) == 3, "the shown text is not repeated and there is exactly one update"
    assert len(fake.stream_calls) == 1
    assert len(fake.generate_calls) == 1
    retry, first = fake.generate_calls[0], fake.stream_calls[0]
    assert retry.system == first.system
    assert retry.contents == [
        *first.contents,
        pl.Turn(role="model", text="Уявіть провал. Що сталося першим?"),
        pl.Turn(role="user", text=RETRY_ASK),
    ]
    assert "reply" not in retry.schema.model_fields
    update = items[2]
    assert type(update) is FacilitatorUpdate
    assert update.model_dump() == {
        "reply": "Уявіть провал. Що сталося першим?",
        "current_phase_id": "a_three",
        "phase_exit_met": False,
        "map_updates": [ADD],
    }


def test_broken_map_updates_after_shown_text_also_retry_the_update() -> None:
    bad = dict(ADD, type="not_an_item_type")
    fake = ScenarioLlm(
        deltas=["Що сталося?"],
        done_raw=answer("Що сталося?", "a_one", False, [bad]),
        generate=[update_only("a_one")],
    )
    items, exc = collect(lambda: respond(context(), knowledge(), fake))
    assert exc is None
    assert len(fake.generate_calls) == 1
    assert "reply" not in fake.generate_calls[0].schema.model_fields
    assert items == [
        ReplyDelta(text="Що сталося?"),
        FacilitatorUpdate(
            reply="Що сталося?", current_phase_id="a_one", phase_exit_met=False, map_updates=[]
        ),
    ]


def test_retry_invalid_after_shown_text_raises_facilitation_error_after_the_same_deltas() -> None:
    fake = ScenarioLlm(
        deltas=["Уявіть провал. ", "Що сталося?"],
        done_raw=answer("Уявіть провал. Що сталося?", "b_one"),
        generate=[update_only("b_two")],
    )
    items, exc = collect(lambda: respond(context(), knowledge(), fake))
    assert isinstance(exc, FacilitationError)
    assert items == [ReplyDelta(text="Уявіть провал. "), ReplyDelta(text="Що сталося?")]
    assert len(fake.generate_calls) == 1


def test_invalid_answer_without_deltas_retries_the_full_answer() -> None:
    fake = ScenarioLlm(
        deltas=[],
        done_raw='{"current_phase_id": "a_one", "phase_exit_met": fal',  # truncated
        generate=[answer(REPLY, "a_two", True)],
    )
    items, exc = collect(lambda: respond(context(), knowledge(), fake))
    assert exc is None
    assert len(fake.generate_calls) == 1
    schema = fake.generate_calls[0].schema
    assert "reply" in schema.model_fields
    with pytest.raises(ValidationError):
        schema.model_validate_json(answer(REPLY, "b_one"))
    assert items == [
        ReplyDelta(text=REPLY),
        FacilitatorUpdate(reply=REPLY, current_phase_id="a_two", phase_exit_met=True, map_updates=[]),
    ]
    assert type(items[1]) is FacilitatorUpdate


def test_full_retry_invalid_raises_facilitation_error_with_nothing_shown() -> None:
    fake = ScenarioLlm(
        deltas=[],
        done_raw=answer_reply_last(REPLY, "b_one"),
        generate=[answer(REPLY, "b_two")],
    )
    items, exc = collect(lambda: respond(context(), knowledge(), fake))
    assert isinstance(exc, FacilitationError)
    assert items == []


def test_llm_unavailable_passes_through_unchanged() -> None:
    boom = pl.LlmUnavailable("stream broke")
    fake = ScenarioLlm(deltas=["Уявіть ", boom], done_raw=answer(REPLY, "a_one"))
    items, exc = collect(lambda: respond(context(), knowledge(), fake))
    assert exc is boom
    assert items == [ReplyDelta(text="Уявіть ")]


def test_everything_yielded_is_a_facilitation_types_instance() -> None:
    fake = ScenarioLlm(
        deltas=["Що ", "сталося?"],
        done_raw=answer("Що сталося?", "b_one"),
        generate=[update_only("a_one")],
    )
    items, exc = collect(lambda: respond(context(), knowledge(), fake))
    assert exc is None
    assert [type(i) for i in items] == [ReplyDelta, ReplyDelta, FacilitatorUpdate]
    fake2 = ScenarioLlm(deltas=["Що?"], done_raw=answer("Що?", "a_one"))
    items2, exc2 = collect(lambda: respond(context(), knowledge(), fake2))
    assert exc2 is None
    assert [type(i) for i in items2] == [ReplyDelta, FacilitatorUpdate]


def test_facilitator_update_reply_must_not_be_empty() -> None:
    with pytest.raises(ValidationError):
        FacilitatorUpdate(reply="", current_phase_id="a_one", phase_exit_met=False, map_updates=[])
