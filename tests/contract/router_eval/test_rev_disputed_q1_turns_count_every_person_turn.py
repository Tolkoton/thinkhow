"""Disputed (Q1): «розмова йде до `end` цієї картки або до N реплік людини» — this file takes the reading
that N counts every turn of the person in the conversation, the opener and «Давай …» included
(slice router-eval; slice tester). Not sealed until the slice planner answers Q1."""

from pathlib import Path

from rev_fakes import PersonLlm, ProductLlm, choose_raw, fac_raw, knowledge, offer_raw, script

OPENER = "Чому в нас падає кількість реєстрацій? Уже місяць менше, і я не розумію, звідки це."


def test_n_turns_of_the_person_count_the_opener_and_the_choice(tmp_path: Path) -> None:
    def router(no: int, text: str) -> str:
        if text.startswith("Давай"):
            return choose_raw("five-whys")
        return offer_raw("five-whys", "issue-tree")

    llm = ProductLlm(router=router, facilitator=lambda no, text: fac_raw("phase_1_define_problem"))
    script("card_conversations").converse_card(
        knowledge(tmp_path), llm, PersonLlm(), "five-whys", OPENER, turns=5
    )
    assert sorted(llm.person_turns()) == [1, 2, 3, 4, 5]
