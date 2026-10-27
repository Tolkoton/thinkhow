"""Contract tests of notes-readers: the router reads `router` notes beside each card they name
(slice tester; written from the contract, not the code)."""

from nr_fakes import (
    ALPHA,
    BETA,
    GAMMA,
    LANGUAGES,
    ORACLE,
    RULE,
    knowledge,
    legacy,
    line_of,
    note,
    note_lines,
    section,
)

from thinkhow.facilitation.route import CARDS_HEAD, router_instruction


def test_seam1_router_note_of_two_cards_stands_in_both_and_in_id_order() -> None:
    both = note("n-1", ["alpha", "beta"], "router", title="Плутають з інверсією")
    second = note("n-2", ["alpha"], "router", title="Допомагав перед запуском")
    # the list holds n-2 first: the order in the section is by `id`, not by the list
    got = router_instruction(knowledge((ALPHA, BETA, GAMMA), [second, both]), None)
    assert note_lines(section(got, "alpha")) == [
        "- Плутають з інверсією. помітили n-1 робити n-1",
        "- Допомагав перед запуском. помітили n-2 робити n-2",
    ]
    assert note_lines(section(got, "beta")) == ["- Плутають з інверсією. помітили n-1 робити n-1"]
    gamma = section(got, "gamma")
    assert "Досвід:" not in gamma.split("\n")
    assert "Плутають з інверсією" not in gamma and "Допомагав перед запуском" not in gamma


def test_seam2_router_sees_only_the_router_note_of_a_shared_card() -> None:
    r = note("x-1", ["alpha"], "router", title="Для роутера")
    f = note("x-2", ["alpha"], "facilitator", title="Для фасилітатора")
    old = legacy("x-3", ["alpha"])
    got = router_instruction(knowledge((ALPHA, BETA), [r, f, old]), None)
    alpha = section(got, "alpha")
    assert note_lines(alpha) == [line_of(r)]
    assert "Для фасилітатора" not in got
    assert "Стара нотатка x-3" not in got


def test_router_note_line_breaks_inside_noticed_and_do_become_spaces() -> None:
    rec = note("b-1", ["beta"], "router", title="Два рядки", noticed="перше\nдруге", do="третє\nчетверте")
    got = router_instruction(knowledge((ALPHA, BETA), [rec]), None)
    assert note_lines(section(got, "beta")) == ["- Два рядки. перше друге третє четверте"]


def test_router_reading_rule_stands_once_after_cards_head_with_a_router_note() -> None:
    rec = note("r-1", ["beta"], "router")
    for lang in LANGUAGES:
        got = router_instruction(knowledge((ALPHA, BETA), [rec]), lang)
        lines = got.split("\n")
        assert lines.count(RULE) == 1, lang
        head = lines.index(CARDS_HEAD)
        first_card = next(i for i, ln in enumerate(lines) if ln.startswith("### "))
        assert head < lines.index(RULE) < first_card, lang


def test_seam3_router_instruction_without_router_notes_is_byte_equal_to_before() -> None:
    fac = [
        note("f-1", ["alpha"], "facilitator"),
        note("f-2", ["alpha", "beta"], "facilitator"),
        legacy("f-3", ["beta"]),
    ]
    for kk, cards in (("both", (ALPHA, BETA)), ("beta", (BETA,))):
        for lang in LANGUAGES:
            key = f"route|{kk}|{lang}"
            assert router_instruction(knowledge(cards, []), lang) == ORACLE[key], (key, "empty")
            assert router_instruction(knowledge(cards, fac), lang) == ORACLE[key], (key, "facilitator only")
