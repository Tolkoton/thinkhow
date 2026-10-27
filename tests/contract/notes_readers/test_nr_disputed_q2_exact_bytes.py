"""Disputed test of notes-readers (Q2 of the slice tester): the exact bytes of a router instruction with a
`router` note. Reading taken: the rule line is the very next line after CARDS_HEAD (no blank line around it),
and `Досвід:` follows the last `Ознаки:` line directly, the section's blank separator staying after the notes.
Not sealed until the slice planner answers Q2."""

from nr_fakes import ALPHA, BETA, ORACLE, RULE, knowledge, note

from thinkhow.facilitation.route import CARDS_HEAD, router_instruction


def test_router_instruction_with_a_note_is_the_old_bytes_plus_the_rule_and_the_experience_lines() -> None:
    rec = note("p-1", ["alpha"], "router", title="Плутають з інверсією")
    before = ORACLE["route|both|None"]
    expected = before.replace(f"{CARDS_HEAD}\n", f"{CARDS_HEAD}\n{RULE}\n", 1).replace(
        "- сигнал alpha\n", "- сигнал alpha\nДосвід:\n- Плутають з інверсією. помітили p-1 робити p-1\n", 1
    )
    assert router_instruction(knowledge((ALPHA, BETA), [rec]), None) == expected
