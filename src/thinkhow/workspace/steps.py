"""The results of the steps a person chose, in `steps.json` of the topic (learning-loop S6, F9).

The question about the latest chosen step is asked once, when the person comes back after a break; the answer
is recognized by an injected `recognize` and stored here. Does NOT remind anyone, ask twice or learn from
`clearer`.
"""

from collections.abc import Callable, Sequence

from thinkhow.facilitation.types import MapItem, ProblemMap, StepOutcome
from thinkhow.platform.storage import Storage
from thinkhow.workspace._paths import JSON
from thinkhow.workspace.model import StepResult, StepsFile, TopicRef

Recognize = Callable[[str, str, str], StepOutcome | None]
Question = Callable[[str], str]


def pending_step(problem_map: ProblemMap, steps: Sequence[StepResult]) -> MapItem | None:
    """The latest chosen step with no record and later than every step asked about already; else None."""
    chosen = [item for item in problem_map.items if item.type == "chosen_step"]
    asked_ids = {s.step_id for s in steps}
    asked_turns = [_turn(item) for item in chosen if item.id in asked_ids]
    after = max(asked_turns, default=0)
    left = [item for item in chosen if item.id not in asked_ids and _turn(item) > after]
    return max(left, key=_turn, default=None)


def _turn(item: MapItem) -> int:
    return int(item.turn.removeprefix("t") or 0)


def read_steps(storage: Storage, ref: TopicRef) -> list[StepResult]:
    """The records of the topic's steps.json; none without the file (a parse error is not recovered)."""
    data = storage.read("users", f"{ref.uid}/{ref.topic_id}/steps.json")
    return [] if data is None else list(StepsFile.model_validate_json(data).steps)


def _write_steps(storage: Storage, ref: TopicRef, steps: Sequence[StepResult]) -> None:
    data = StepsFile(steps=list(steps)).model_dump_json().encode()
    storage.write("users", f"{ref.uid}/{ref.topic_id}/steps.json", data, JSON)


def step_results_for_learning(storage: Storage, ref: TopicRef) -> list[StepResult]:
    """Read only, no access rule: for learning, with refs from all_topics_for_learning."""
    return read_steps(storage, ref)
