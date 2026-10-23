"""Disputed (Q1): the contract writes the rule with a language over two lines inside one code span
(«…важливіше» / «за «мовою…»»). Read as Markdown, the break is one space; these tests take that reading
and compare the text exactly. Not sealed until the slice planner answers Q1."""

from vrl_fakes import ALPHA, HEAD, MEMORY, RULE_PL, RULES

from thinkhow.facilitation.respond import language_rule, system_instruction

PL = "Polski (pl-PL)"


def test_q1_language_rule_with_language_is_exactly_the_contract_text() -> None:
    assert language_rule(PL) == RULE_PL


def test_q1_system_instruction_section_is_exactly_rules_head_rule_newline() -> None:
    assert system_instruction(ALPHA, MEMORY, PL).startswith(RULES + "\n\n" + HEAD + RULE_PL + "\n")
