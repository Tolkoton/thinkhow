"""Contract tests of step-results (learning-loop S6): `recognize_step` — one model call.

Slice tester; from the contract `.engine/slices/step-results.md`, not the code.
"""

import re

from stp_fakes import STEP, ScenarioLlm

from thinkhow.facilitation import StepOutcome, recognize_step

QUESTION = "Минулого разу ви обрали крок «Поговорити з трьома клієнтами». Як він вийшов?"
TEXT = "Не вийшло: ніхто не відповів на дзвінки."


def test_one_generate_json_with_the_step_outcome_schema_returns_its_answer() -> None:
    llm = ScenarioLlm(
        answer=lambda schema: {
            "answered": True,
            "outcome": "not_worked",
            "clearer": "no",
            "said": "ніхто не відповів",
        }
    )
    got = recognize_step(STEP, QUESTION, TEXT, llm)
    assert got == StepOutcome(answered=True, outcome="not_worked", clearer="no", said="ніхто не відповів")
    assert len(llm.calls) == 1
    assert llm.calls[0].schema is StepOutcome


def test_the_instruction_is_in_ukrainian_and_the_call_carries_the_step_the_question_and_the_text() -> None:
    llm = ScenarioLlm(answer=lambda schema: {"answered": False, "outcome": None, "clearer": None, "said": ""})
    recognize_step(STEP, QUESTION, TEXT, llm)
    (call,) = llm.calls
    assert re.search(r"[ІіЇїЄєҐґ]", call.system), call.system
    whole = call.system + "\n" + call.text
    for part in (STEP, QUESTION, TEXT):
        assert part in whole, part
