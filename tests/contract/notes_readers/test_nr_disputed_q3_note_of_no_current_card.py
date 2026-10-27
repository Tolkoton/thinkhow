"""Disputed test of notes-readers (Q3 of the slice tester): a `router` note whose `cards` name no card of the
current state. Reading taken: no card has a router note, so the instruction stays byte-equal to before and the
rule line does not appear. Not sealed until the slice planner answers Q3."""

from nr_fakes import ALPHA, BETA, ORACLE, knowledge, note

from thinkhow.facilitation.route import router_instruction


def test_router_note_naming_only_an_absent_card_leaves_the_instruction_as_before() -> None:
    rec = note("z-1", ["zeta"], "router")
    assert router_instruction(knowledge((ALPHA, BETA), [rec]), None) == ORACLE["route|both|None"]
