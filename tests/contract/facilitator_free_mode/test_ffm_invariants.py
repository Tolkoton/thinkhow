"""Contract tests of facilitator-free-mode: the invariants I1-I4 (slice tester; from the contract)."""

import json
from functools import partial
from typing import Any

import pytest
from ffm_fakes import (
    ALPHA,
    HISTORY,
    ITEM,
    MEMORY,
    RULES,
    SOLO,
    STATE_LINE,
    ScenarioLlm,
    answer,
    answer_reply_last,
    collect,
    context,
    knowledge,
    update_only,
)
from pydantic import ValidationError

from thinkhow.facilitation import FacilitatorUpdate, ProblemMap, ReplyDelta, respond
from thinkhow.facilitation.respond import answer_schema, update_schema
from thinkhow.platform import llm as pl
from thinkhow.workspace.topics import apply_updates

REPLY = "Яка ваша ціль на цей рік?"


def test_I1_schemas_accept_exactly_the_cards_phases_and_null() -> None:
    not_phases_of = {
        "alpha": ["b_one", "s_only", "phase_1_time_travel", "", "null", "A_ONE", "a_one "],
        "solo": ["a_one", "b_two", "s_ONLY", "", "null", "s_only "],
    }
    for card, phases in ((ALPHA, ["a_one", "a_two", "a_three"]), (SOLO, ["s_only"])):
        full, upd = answer_schema(card), update_schema(card)
        for phase in [*phases, None]:
            full.model_validate_json(answer(REPLY, phase))
            upd.model_validate_json(update_only(phase))
        for bad in not_phases_of[card.id]:
            with pytest.raises(ValidationError):
                full.model_validate_json(answer(REPLY, bad))
            with pytest.raises(ValidationError):
                upd.model_validate_json(update_only(bad))


def _settled(fake: ScenarioLlm) -> FacilitatorUpdate:
    items, exc = collect(partial(respond, context(), knowledge(), fake))
    assert exc is None, repr(exc)
    assert isinstance(items[-1], FacilitatorUpdate)
    assert all(isinstance(i, ReplyDelta) for i in items[:-1])
    return items[-1]


def test_I2_returned_phase_or_null_reaches_the_update_and_the_map() -> None:
    for phase in (None, "a_three"):
        scenarios = {
            "valid with deltas": ScenarioLlm(
                deltas=["Яка ваша ціль ", "на цей рік?"], done_raw=answer(REPLY, phase)
            ),
            "valid without deltas": ScenarioLlm(deltas=[], done_raw=answer_reply_last(REPLY, phase)),
            "invalid with deltas": ScenarioLlm(
                deltas=[REPLY], done_raw=answer(REPLY, "b_one"), generate=[update_only(phase)]
            ),
            "invalid without deltas": ScenarioLlm(
                deltas=[],
                done_raw='{"current_phase_id": null, "phase_exit_met": fal',
                generate=[answer(REPLY, phase)],
            ),
        }
        for branch, fake in scenarios.items():
            update = _settled(fake)
            assert update.current_phase_id == phase, (branch, phase)
            assert update.reply == REPLY, (branch, phase)
            before = ProblemMap(items=[ITEM], phase_id="a_two" if phase is None else None, last_turn=1)
            after = apply_updates(before, update, 3)
            assert after.phase_id == phase, (branch, phase)


def test_I3_system_instruction_starts_with_the_new_rules_verbatim() -> None:
    cases: list[tuple[str, list[Any], str | None]] = [
        ("alpha", list(MEMORY), None),
        ("solo", [], "Українська (uk-UA)"),
        ("beta", list(MEMORY), "Polski (pl-PL)"),
    ]
    for card_id, memory, language in cases:
        phase = {"alpha": "a_one", "solo": "s_only", "beta": "b_one"}[card_id]
        fake = ScenarioLlm(deltas=[REPLY], done_raw=answer(REPLY, phase))
        _, exc = collect(
            partial(respond, context(card_id=card_id, language=language), knowledge(memory=memory), fake)
        )
        assert exc is None, repr(exc)
        system = fake.stream_calls[0].system
        assert system.startswith(RULES + "\n\n# Мова відповіді\n"), (card_id, language)
        assert "скажи в reply, що час змінити метод" not in system[: len(RULES)]


def _frame(pmap: ProblemMap, turn_no: int, text: str, history: list[Any]) -> str:
    fake = ScenarioLlm(deltas=[REPLY], done_raw=answer(REPLY, "a_one"))
    _, exc = collect(
        partial(
            respond, context(problem_map=pmap, turn_no=turn_no, text=text, history=history), knowledge(), fake
        )
    )
    assert exc is None, repr(exc)
    contents = fake.stream_calls[0].contents
    assert contents[:-1] == [pl.Turn(role=t.role, text=t.text) for t in history]
    last = contents[-1]
    assert last.role == "user"
    return last.text


def test_I4_state_line_iff_phase_is_null_and_last_turn_above_zero() -> None:
    head = "[Карта проблеми зараз]\n"
    item_json = {"id": "i1", "type": "goal", "text": "заробити більше", "turn": "t1"}
    cases = [
        # (phase_id, last_turn, items, turn_no, text, history, state line expected)
        (None, 1, [ITEM], 3, "Не знаю, з чого почати.", list(HISTORY), True),
        (None, 13, [], 14, "А як це дізнатися?\nПідкажіть.", list(HISTORY), True),
        (None, 1, [ITEM], 2, "Так", [], True),
        (None, 0, [], 1, "Хочу заробити більше.", [], False),
        (None, 0, [ITEM], 1, "Хочу заробити більше.", list(HISTORY), False),
        ("a_one", 1, [ITEM], 3, "Не знаю, з чого почати.", list(HISTORY), False),
        ("a_three", 13, [], 14, "Що далі?", list(HISTORY), False),
        ("a_two", 0, [], 1, "План є.", [], False),
    ]
    for phase_id, last_turn, items, turn_no, text, history, expected in cases:
        pmap = ProblemMap(items=items, phase_id=phase_id, last_turn=last_turn)
        frame = _frame(pmap, turn_no, text, history)
        case = (phase_id, last_turn, turn_no)
        tail = f"\n\n[Репліка людини #{turn_no}]\n{text}"
        assert frame.startswith(head), case
        assert frame.endswith(tail), case
        middle = frame[len(head) : len(frame) - len(tail)]
        state = "\n\n" + STATE_LINE
        if expected:
            assert middle.endswith(state), case
            map_json = middle[: -len(state)]
        else:
            assert "[Стан]" not in frame, case
            map_json = middle
        assert json.loads(map_json) == {
            "items": [item_json] if items else [],
            "phase_id": phase_id,
            "last_turn": last_turn,
        }, case
