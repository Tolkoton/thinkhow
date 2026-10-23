"""Contract tests of voice-reply-language: the language section of the instruction (slice tester; from the
contract, not the code). Whitespace inside the rule with a language is compared collapsed (question Q1)."""

from functools import partial

from vrl_fakes import (
    ALPHA,
    HEAD,
    MEMORY,
    RULE_NONE,
    RULE_PL,
    RULES,
    ScenarioLlm,
    answer,
    collect,
    context,
    knowledge,
    rule_with,
    squash,
    update_only,
)

from thinkhow.facilitation.respond import language_rule, respond, system_instruction
from thinkhow.knowledge import card_prompt

PL = "Polski (pl-PL)"
REPLY = "Co może pójść nie tak?"


def section_of(system: str) -> str:
    """The text between «# Мова відповіді» (right after the rules) and «# Картка» with the card."""
    prefix = RULES + "\n\n" + HEAD
    assert system.startswith(prefix), "the instruction does not start with rules.md, then «# Мова відповіді»"
    card_at = system.find("# Картка\n" + card_prompt(ALPHA), len(prefix))
    assert card_at != -1, "no «# Картка» with the card after the language section"
    assert system.find("# Пам'ять досвіду", card_at) != -1, "no «# Пам'ять досвіду» after the card"
    section = system[len(prefix) : card_at]
    assert section.endswith("\n")
    return section


def test_language_rule_with_language_is_the_contract_text() -> None:
    assert squash(language_rule(PL)) == squash(RULE_PL)


def test_language_rule_without_language_is_the_contract_text() -> None:
    assert language_rule(None) == RULE_NONE


def test_language_rule_empty_string_takes_the_branch_with_a_language() -> None:
    assert squash(language_rule("")) == squash(rule_with(""))


def test_system_instruction_puts_the_language_section_between_rules_and_card() -> None:
    section = section_of(system_instruction(ALPHA, MEMORY, PL))
    assert squash(section) == squash(RULE_PL)


def test_system_instruction_without_language_argument_carries_the_no_language_rule() -> None:
    section = section_of(system_instruction(ALPHA, MEMORY))
    assert section.rstrip("\n") == RULE_NONE


def test_respond_sends_the_context_language_in_the_section() -> None:
    fake = ScenarioLlm(deltas=[REPLY], done_raw=answer(REPLY, "a_one"))
    items, exc = collect(lambda: respond(context(PL), knowledge(), fake))
    assert exc is None
    section = section_of(fake.stream_calls[0].system)
    assert squash(section) == squash(RULE_PL)


def test_respond_without_context_language_sends_the_no_language_rule() -> None:
    fake = ScenarioLlm(deltas=[REPLY], done_raw=answer(REPLY, "a_one"))
    items, exc = collect(lambda: respond(context(None), knowledge(), fake))
    assert exc is None
    assert section_of(fake.stream_calls[0].system).rstrip("\n") == RULE_NONE


def test_update_retry_sends_the_same_instruction_with_the_language() -> None:
    # the streamed answer names a phase of another card: the update is retried (`_settle`)
    fake = ScenarioLlm(deltas=[REPLY], done_raw=answer(REPLY, "b_one"), generate=[update_only("a_two")])
    items, exc = collect(lambda: respond(context(PL), knowledge(), fake))
    assert exc is None
    assert len(fake.generate_calls) == 1
    assert fake.generate_calls[0].system == fake.stream_calls[0].system
    assert squash(section_of(fake.generate_calls[0].system)) == squash(RULE_PL)


def test_rules_md_verbatim_first_with_and_without_language() -> None:
    for language in (PL, None):
        fake = ScenarioLlm(deltas=[REPLY], done_raw=answer(REPLY, "a_one"))
        collect(partial(respond, context(language), knowledge(), fake))
        assert fake.stream_calls[0].system.startswith(RULES + "\n\n" + HEAD), language
