"""Disputed (Q1): «2–3 різні кандидати» read as different cards — the same card_id twice with different `why`
is refused. Not sealed until the slice planner answers (slice tester; from the contract)."""

import pytest
from pydantic import ValidationError
from rt_fakes import PROFILE

from thinkhow.facilitation.route import RouterAnswer


def test_q1_offer_naming_one_card_twice_with_different_whys_is_refused() -> None:
    for candidates in (
        [("alpha", "перше пояснення"), ("alpha", "друге пояснення")],
        [("alpha", "перше пояснення"), ("beta", "w"), ("alpha", "друге пояснення")],
    ):
        with pytest.raises(ValidationError):
            RouterAnswer.model_validate(
                {
                    "action": "offer",
                    "profile": PROFILE,
                    "candidates": [{"card_id": c, "why": w} for c, w in candidates],
                    "card_id": None,
                    "reply": "Котрий ближчий?",
                    "why": "чому",
                }
            )
