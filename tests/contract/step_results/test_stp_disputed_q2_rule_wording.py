"""Disputed test of step-results (Q2): the analysis rule about step results, in the contract's words.

Slice tester; from the contract `.engine/slices/step-results.md`, not the code. Not sealed until the slice
planner answers Q2: the contract quotes the rule («…»), but does not say whether the words are literal.
"""

from thinkhow.learning.analyze import ANALYZER

RULE = "результат кроку — що він каже про спосіб думати, яким людина дійшла до кроку"


def test_q2_the_analyzer_instruction_holds_the_step_result_rule_word_for_word() -> None:
    assert RULE.lower() in ANALYZER.lower()
