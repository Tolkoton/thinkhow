"""Contract tests of step-results (learning-loop S6): `pending_step` — which step the question is about.

Slice tester; from the contract `.engine/slices/step-results.md`, not the code.
"""

from stp_fakes import T0

from thinkhow.facilitation.types import MapItem, ProblemMap
from thinkhow.workspace import StepResult, pending_step


def item(item_id: str, turn: int, kind: str = "chosen_step") -> MapItem:
    return MapItem.model_validate(
        {"id": item_id, "type": kind, "text": f"крок {item_id}", "turn": f"t{turn}"}
    )


def record(step_id: str, asked_turn: int) -> StepResult:
    return StepResult(
        step_id=step_id,
        step=f"крок {step_id}",
        asked_turn=asked_turn,
        outcome=None,
        clearer=None,
        said="",
        at=T0,
    )


def test_no_chosen_step_is_none() -> None:
    assert pending_step(ProblemMap(items=[]), []) is None
    others = ProblemMap(
        items=[item("g1", 1, "goal"), item("p1", 2, "plan"), item("o1", 3, "option_considered")]
    )
    assert pending_step(others, []) is None


def test_one_chosen_step_without_a_record_is_that_item() -> None:
    problem_map = ProblemMap(items=[item("g1", 1, "goal"), item("s1", 4)])
    assert pending_step(problem_map, []) == item("s1", 4)


def test_a_chosen_step_with_a_record_is_none() -> None:
    problem_map = ProblemMap(items=[item("s1", 4)])
    assert pending_step(problem_map, [record("s1", 7)]) is None


def test_of_several_chosen_steps_the_latest_by_turn_number_not_by_text_or_place() -> None:
    # t10 is later than t9 by number; it stands first in the list
    problem_map = ProblemMap(items=[item("late", 10), item("early", 9), item("g1", 11, "goal")])
    assert pending_step(problem_map, []) == item("late", 10)


def test_an_older_step_replaced_by_one_already_asked_about_is_never_asked_a_newer_one_is() -> None:
    asked = [record("s7", 11)]
    older = ProblemMap(items=[item("s5", 5), item("s7", 7)])
    assert pending_step(older, asked) is None
    newer = ProblemMap(items=[item("s5", 5), item("s7", 7), item("s13", 13)])
    assert pending_step(newer, asked) == item("s13", 13)
