"""Contract tests of deep-change-question, hardest seam 4: the schema field `DeepPlan.question`, the rule
«План» of `deep.md`, and the state line `CHANGE_LINE` in the plan's frame only on a change (slice tester;
from the contract «Seam», not the code)."""

import re
from typing import Any

from dcq_fakes import CHANGE, CHANGE_PREFIX, DQ, DQ2, dc, plan_with

from thinkhow.facilitation import deep
from thinkhow.facilitation.types import DeepPlan, FacilitatorUpdate, ReplyDelta


def test_deep_plan_has_an_optional_question_field_where_empty_and_blank_are_valid() -> None:
    schema = DeepPlan.model_json_schema()
    assert "question" in schema["properties"]
    assert "question" not in schema.get("required", [])
    for value in (None, "", "   "):
        DeepPlan.model_validate_json(plan_with(dc.INTRO_1, dc.PLAN_1, value))
    given: Any = DeepPlan.model_validate_json(plan_with(dc.INTRO_1, dc.PLAN_1, DQ2))
    assert given.question == DQ2
    plan: Any = DeepPlan.model_validate_json(plan_with(dc.INTRO_1, dc.PLAN_1))
    assert plan.question is None
    assert (plan.intro, list(plan.questions)) == (dc.INTRO_1, [dc.QA, dc.QB, dc.QC])


def test_the_plan_rule_names_the_change_state_line_and_the_question_field() -> None:
    rule = deep.RULES["План"]
    assert CHANGE_PREFIX in rule
    assert re.search(r"\bquestion\b", rule)


def test_change_line_is_a_module_constant_starting_with_the_state_words() -> None:
    assert hasattr(deep, "CHANGE_LINE")
    line: Any = dc.api(deep, "CHANGE_LINE")
    assert isinstance(line, str)
    assert line.startswith(CHANGE_PREFIX)


def test_the_plan_frame_carries_the_change_line_before_the_persons_reply_only_on_a_change() -> None:
    changed = dc.DcLlm(plans=[dc.PLAN_RAW_2])
    pending = dc.pending(DQ, dc.INTRO_1, dc.PLAN_1)
    list(deep.deep_changed(pending, dc.context(text=CHANGE), changed, dc.REV))
    frame = changed.of("plan")[0].text
    assert CHANGE_PREFIX in frame
    line: str = dc.api(deep, "CHANGE_LINE")
    assert line + "\n\n" in frame
    assert frame.index(line + "\n\n") < frame.rindex(CHANGE)

    offer = dc.DcLlm(plans=[dc.PLAN_RAW_1])
    list(deep.deep_offer(DQ, dc.context(), offer, dc.REV))
    assert CHANGE_PREFIX not in offer.of("plan")[0].text

    card = dc.DcLlm(plans=[dc.PLAN_RAW_1])
    items: list[Any] = [
        ReplyDelta(text=dc.CARD_REPLY),
        FacilitatorUpdate(
            reply=dc.CARD_REPLY, current_phase_id="a_one", phase_exit_met=False, map_updates=[]
        ),
    ]
    list(deep.with_deep(iter(items), lambda: DQ, dc.context(), card, dc.REV))
    assert CHANGE_PREFIX not in card.of("plan")[0].text
