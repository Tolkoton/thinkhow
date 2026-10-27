"""Contract tests of notes-readers: the facilitator reads only the `facilitator` notes of its own card
(slice tester; written from the contract, not the code)."""

from nr_fakes import (
    ALPHA,
    BETA,
    GAMMA,
    LANGUAGES,
    ORACLE,
    legacy,
    memory_section,
    note,
)

from thinkhow.facilitation.respond import system_instruction
from thinkhow.knowledge import MemoryRecord


def block_head(rec: MemoryRecord) -> str:
    return f"### {rec.id} — {rec.title}"


def test_seam1_facilitator_note_of_two_cards_stands_in_both_not_in_a_third() -> None:
    rec = note("m-1", ["alpha", "beta"], "facilitator", title="Спільна нотатка")
    for c in (ALPHA, BETA):
        assert block_head(rec) in memory_section(system_instruction(c, [rec])), c.id
    assert "Спільна нотатка" not in system_instruction(GAMMA, [rec])


def test_seam2_facilitator_sees_only_facilitator_and_old_notes_of_a_shared_card() -> None:
    r = note("x-1", ["alpha"], "router", title="Для роутера")
    f = note("x-2", ["alpha"], "facilitator", title="Для фасилітатора")
    old = legacy("x-3", ["alpha"])
    got = memory_section(system_instruction(ALPHA, [r, f, old]))
    assert block_head(f) in got
    assert block_head(old) in got
    assert "Для роутера" not in got


def test_facilitator_memory_without_own_notes_is_empty_as_before() -> None:
    # M-1 of the oracle's inputs names only `alpha`; a router note on `beta` is not the facilitator's
    noise = [
        MemoryRecord(
            id="M-1",
            title="Досвід",
            cards=["alpha"],
            noticed="людина поспішає",
            do="повернути до фази",
            basis="3 сесії.",
        ),
        note("r-1", ["beta"], "router"),
    ]
    for lang in LANGUAGES:
        for routed in (False, True):
            key = f"respond|beta|empty|{lang}|{routed}"
            assert system_instruction(BETA, noise, lang, routed) == ORACLE[key], key


def test_facilitator_memory_holds_its_own_note_in_the_same_form_as_before() -> None:
    own = MemoryRecord(
        id="M-1",
        title="Досвід",
        cards=["alpha"],
        noticed="людина поспішає",
        do="повернути до фази",
        basis="3 сесії.",
    )
    memory = [own, note("f-9", ["beta"], "facilitator"), note("r-9", ["alpha"], "router")]
    for lang in LANGUAGES:
        for routed in (False, True):
            key = f"respond|alpha|one|{lang}|{routed}"
            assert system_instruction(ALPHA, memory, lang, routed) == ORACLE[key], key
