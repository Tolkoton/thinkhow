"""Contract tests of deep-research-confirm-first: the new types of `facilitation/types.py` and the sections of
`deep.md` (slice tester; from the contract «Seam», not the code)."""

import dataclasses

import pytest
from dc_fakes import DQ, INTRO_1, QA, QB, QC, QD, QE, api, context, pending
from pydantic import ValidationError

from thinkhow.facilitation import deep
from thinkhow.facilitation import types as ft


def test_pending_deep_holds_question_intro_and_two_to_four_non_empty_sub_questions() -> None:
    got = pending(DQ, INTRO_1, [QA, QB, QC])
    assert (got.question, got.intro, list(got.questions)) == (DQ, INTRO_1, [QA, QB, QC])
    assert list(pending(DQ, INTRO_1, [QA, QB]).questions) == [QA, QB]
    assert list(pending(DQ, INTRO_1, [QA, QB, QC, QD]).questions) == [QA, QB, QC, QD]
    for question, intro, questions in (
        (DQ, INTRO_1, [QA]),
        (DQ, INTRO_1, [QA, QB, QC, QD, QE]),
        (DQ, INTRO_1, [QA, ""]),
        ("", INTRO_1, [QA, QB]),
        (DQ, "", [QA, QB]),
    ):
        with pytest.raises(ValidationError):
            pending(question, intro, questions)


def test_deep_consent_answer_is_one_of_four_words_and_has_no_own_time_limit() -> None:
    consent = api(ft, "DeepConsent")
    for word in ("yes", "change", "no", "other"):
        assert consent.model_validate_json(f'{{"answer": "{word}"}}').answer == word
    for bad in ('{"answer": "maybe"}', '{"answer": true}', "{}"):
        with pytest.raises(ValidationError):
            consent.model_validate_json(bad)
    assert not hasattr(consent, "llm_timeout_s")


def test_deep_proposed_is_a_frozen_event_carrying_the_pending_proposal() -> None:
    proposal = pending(DQ, INTRO_1, [QA, QB])
    event = api(ft, "DeepProposed")(proposal)
    assert event.pending == proposal
    with pytest.raises(dataclasses.FrozenInstanceError):
        event.pending = pending(DQ, INTRO_1, [QC, QD])


def test_facilitation_context_has_pending_deep_none_and_deep_off_false_by_default() -> None:
    ctx = context()
    assert api(ctx, "pending_deep") is None
    assert api(ctx, "deep_off") is False
    proposal = pending(DQ, INTRO_1, [QA, QB])
    given = context(pending_deep=proposal, deep_off=True)
    assert api(given, "pending_deep") == proposal and api(given, "deep_off") is True


def test_deep_md_has_the_three_sections_and_the_new_fourth_one_consent() -> None:
    assert set(deep.RULES) == {"План", "Пошук", "Звіт", "Згода"}
    assert all(deep.RULES[name].strip() for name in deep.RULES)
