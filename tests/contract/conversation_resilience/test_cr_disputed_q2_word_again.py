"""Contract tests of conversation-resilience: disputed (Q2), not sealed until the slice planner answers."""

from cr_fakes import HERE, run_node_test

FILE = HERE / "cr_disputed_q2_word_again.test.mjs"


def test_Q2_after_a_cut_at_the_end_the_word_rule_applies_again_to_the_word_now_at() -> None:
    run_node_test(FILE, "Q2: after a cut at the end the word rule applies again to the word now at the end")
