"""Disputed (Q2): the `why` of an `end` decision is exactly «картку пройдено» / «картка не підходить».
Not sealed until the slice planner answers (slice tester; from the contract)."""

from rt_cards import problem_map
from rt_fakes import RecordingLead, RouterLlm, context, d_choose, events, knowledge, led, run_converse


def test_q2_end_why_is_the_contract_text_word_for_word() -> None:
    for phase, met, why in ((None, False, "картка не підходить"), ("a_three", True, "картку пройдено")):
        lead = RecordingLead([led(phase, exit_met=met)])
        ctx = context((d_choose(1, "alpha"),), pm=problem_map("a_two", 2))
        items, err = run_converse(ctx, knowledge(), RouterLlm(), lead)
        assert err is None, err
        (decision,) = events(items)
        assert decision.why == why
