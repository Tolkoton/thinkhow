"""Contract tests of notes-readers: the invariants I1-I2 (slice tester; from the contract, not the code).

The inputs are chosen by hand from each invariant's «Domain»: the empty memory, a note of no card, of two
cards, of an id no card has, the same card named twice, both audiences on one card,
an old record without `audience`.
"""

from collections.abc import Sequence

from nr_fakes import (
    ALPHA,
    BETA,
    GAMMA,
    before_experience,
    knowledge,
    legacy,
    line_of,
    memory_section,
    note,
    section,
)

from thinkhow.facilitation.respond import system_instruction
from thinkhow.facilitation.route import router_instruction
from thinkhow.knowledge import MemoryRecord, card_prompt

CARDS = (ALPHA, BETA, GAMMA)

MEMORIES: list[Sequence[MemoryRecord]] = [
    [],
    [note("a-1", ["alpha", "beta"], "router")],
    [note("a-2", [], "router"), note("a-3", [], "facilitator")],
    [note("a-4", ["alpha", "alpha"], "router"), note("a-5", ["gamma", "gamma"], "facilitator")],
    [note("a-6", ["zeta", "beta"], "router"), note("a-7", ["zeta", "gamma"], "facilitator")],
    [note("a-8", ["gamma"], "router"), note("a-9", ["gamma"], "facilitator"), legacy("b-1", ["gamma"])],
    [
        note("c-1", ["alpha", "beta", "gamma"], "facilitator"),
        legacy("c-2", ["beta"]),
        note("c-3", ["beta", "gamma"], "router"),
        note("c-0", ["gamma"], "router"),
    ],
]

# the expected owners, written by hand: record id -> (router cards, facilitator cards)
WHERE: dict[str, tuple[set[str], set[str]]] = {
    "a-1": ({"alpha", "beta"}, set()),
    "a-2": (set(), set()),
    "a-3": (set(), set()),
    "a-4": ({"alpha"}, set()),
    "a-5": (set(), {"gamma"}),
    "a-6": ({"beta"}, set()),
    "a-7": (set(), {"gamma"}),
    "a-8": ({"gamma"}, set()),
    "a-9": (set(), {"gamma"}),
    "b-1": (set(), {"gamma"}),
    "c-1": (set(), {"alpha", "beta", "gamma"}),
    "c-2": (set(), {"beta"}),
    "c-3": ({"beta", "gamma"}, set()),
    "c-0": ({"gamma"}, set()),
}


def test_I1_a_note_is_seen_only_by_its_audience_and_only_beside_its_cards() -> None:
    for memory in MEMORIES:
        router = router_instruction(knowledge(CARDS, memory), None)
        for c in CARDS:
            sec = section(router, c.id)
            mem = memory_section(system_instruction(c, memory))
            for rec in memory:
                in_router, in_facilitator = WHERE[rec.id]
                where = (rec.id, c.id)
                if c.id in in_router:
                    assert line_of(rec) in sec.split("\n"), where
                else:
                    assert rec.title not in sec, where
                if c.id in in_facilitator:
                    assert f"### {rec.id} — {rec.title}" in mem.split("\n"), where
                else:
                    assert rec.title not in mem, where


def test_I2_the_card_half_of_each_instruction_does_not_depend_on_memory() -> None:
    plain = router_instruction(knowledge(CARDS, []), None)
    for memory in MEMORIES:
        router = router_instruction(knowledge(CARDS, memory), None)
        for c in CARDS:
            assert before_experience(section(router, c.id)) == before_experience(section(plain, c.id)), c.id
            system = system_instruction(c, memory)
            assert f"# Картка\n{card_prompt(c)}\n# Пам'ять досвіду\n" in system, c.id
