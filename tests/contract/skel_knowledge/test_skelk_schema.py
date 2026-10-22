"""Contract tests of skel-knowledge: schema.py (slice tester; written from the contract, not the code)."""

from typing import Any

import pytest
from pydantic import ValidationError
from skelk_fakes import card_dict, phase_dict

from thinkhow.knowledge import Card, ChangeRecord, FacilitatorHalf, MemoryRecord, Phase, RouterHalf


def memory_dict(mid: str) -> dict[str, Any]:
    return {"id": mid, "title": "t", "cards": ["pre-mortem"], "noticed": "n", "do": "d", "basis": "b"}


def test_phase_id_follows_its_pattern() -> None:
    for good in ("a", "phase_1_time_travel", "0", "z" * 64):
        assert Phase.model_validate(phase_dict(good)).id == good
    for bad in ("", "phase-1", "Phase_1", "фаза", "a b", "z" * 65):
        with pytest.raises(ValidationError):
            Phase.model_validate(phase_dict(bad))


def test_phase_goal_and_exit_must_not_be_empty() -> None:
    with pytest.raises(ValidationError):
        Phase.model_validate({**phase_dict("p"), "goal": ""})
    with pytest.raises(ValidationError):
        Phase.model_validate({**phase_dict("p"), "exit": ""})


def test_router_half_when_yes_and_when_no_must_not_be_empty() -> None:
    router = card_dict("c")["router"]
    assert RouterHalf.model_validate(router).when_yes == ["роутер-так c"]
    with pytest.raises(ValidationError):
        RouterHalf.model_validate({**router, "when_yes": []})
    with pytest.raises(ValidationError):
        RouterHalf.model_validate({**router, "when_no": []})


def test_facilitator_half_needs_phases_with_distinct_ids() -> None:
    half = card_dict("c")["facilitator"]
    assert [p.id for p in FacilitatorHalf.model_validate(half).phases] == ["p_one", "p_two"]
    with pytest.raises(ValidationError):
        FacilitatorHalf.model_validate({**half, "phases": []})
    with pytest.raises(ValidationError):
        FacilitatorHalf.model_validate(
            {**half, "phases": [phase_dict("same"), phase_dict("same", exit_text="x")]}
        )


def test_card_id_follows_its_pattern() -> None:
    for good in ("pre-mortem", "a", "wrap-2", "c" * 64):
        assert Card.model_validate(card_dict(good)).id == good
    for bad in ("", "pre_mortem", "Pre-mortem", "pre mortem", "c" * 65):
        with pytest.raises(ValidationError):
            Card.model_validate(card_dict(bad))


def test_memory_record_id_follows_its_pattern_capitals_allowed() -> None:
    for good in ("M-001", "m-1", "ABC", "M" * 64):
        assert MemoryRecord.model_validate(memory_dict(good)).id == good
    for bad in ("", "M_001", "M 001", "М-001", "M" * 65):
        with pytest.raises(ValidationError):
            MemoryRecord.model_validate(memory_dict(bad))


def test_change_record_rev_is_at_least_one() -> None:
    base = {"what": "w", "why": "y", "cards": {"a": "knowledge/cards/a/v1.json"}, "memory": {}}
    assert ChangeRecord.model_validate({**base, "rev": 1}).rev == 1
    for bad in (0, -1):
        with pytest.raises(ValidationError):
            ChangeRecord.model_validate({**base, "rev": bad})
