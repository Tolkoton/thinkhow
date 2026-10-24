"""Disputed (Q2): the contract says «розмову позначено «картку не запропоновано»» and «у звіті рядок «людина
назвала метод» (якщо так — розмову позначено)» without naming where — the conversation's own report or its row
of `index.md`. This file takes the reading that the mark stands in the text `index()` returns
(slice router-eval; slice tester). Not sealed until the slice planner answers Q2."""

from pathlib import Path

from rev_fakes import STAMP, PersonLlm, ProductLlm, choose_raw, fac_raw, knowledge, offer_raw, script

OPENER = "Чому в нас падає кількість реєстрацій? Уже місяць менше, і я не розумію, звідки це."


def test_target_not_offered_index_says_the_card_was_not_offered(tmp_path: Path) -> None:
    def router(no: int, text: str) -> str:
        if text.startswith("Давай"):
            return choose_raw("issue-tree")
        return offer_raw("issue-tree", "scamper")

    plan = {2: fac_raw("phase_1_root_question"), 3: fac_raw("phase_4_deepen_and_next", True)}
    llm = ProductLlm(
        router=router, facilitator=lambda no, text: plan.get(no, fac_raw("phase_1_root_question"))
    )
    cc = script("card_conversations")
    conv = cc.converse_card(knowledge(tmp_path), llm, PersonLlm(), "five-whys", OPENER, turns=12)
    assert "картку не запропоновано" in cc.index([conv], STAMP)


def test_a_person_turn_that_names_a_method_is_marked_in_index(tmp_path: Path) -> None:
    def router(no: int, text: str) -> str:
        if text.startswith("Давай"):
            return choose_raw("five-whys")
        return offer_raw("five-whys", "issue-tree")

    plan = {2: fac_raw("phase_1_define_problem"), 3: fac_raw("phase_3_reverse_check_and_change", True)}
    llm = ProductLlm(
        router=router, facilitator=lambda no, text: plan.get(no, fac_raw("phase_1_define_problem"))
    )
    person = PersonLlm(replies=["Спробуймо weighted-matrix."])
    cc = script("card_conversations")
    conv = cc.converse_card(knowledge(tmp_path), llm, person, "five-whys", OPENER, turns=12)
    assert "людина назвала метод" in cc.index([conv], STAMP)
