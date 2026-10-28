"""Task 713 (overseer test gap, unit 3 of router-eval): the index row of a --switch conversation judges
the card switched FROM. Kept outside the sealed `test_rev_conversations.py`: the builder does not edit
the tester's files."""

from pathlib import Path

from rev_fakes import STAMP, PersonLlm, ProductLlm, choose_raw, fac_raw, knowledge, offer_raw, script

OPENER = "Чому в нас падає кількість реєстрацій? Уже місяць менше, і я не розумію, звідки це."


def test_switch_then_another_card_chosen_and_unfinished_the_row_judges_the_card_switched_from(
    tmp_path: Path,
) -> None:
    """Task 713 (overseer test gap): after «Давай інакше» the router ends weighted-matrix not_fit and
    `choose`s five-whys, which never reaches `end`. The row's «end» is the end of the card switched FROM."""

    cc = script("card_conversations")

    def router(no: int, text: str) -> str:
        if no == 1:
            return offer_raw("weighted-matrix", "issue-tree")
        if text.startswith("Давай"):
            return choose_raw("weighted-matrix")
        return choose_raw("five-whys")

    def fac(no: int, text: str) -> str:
        if text == cc.SWITCH_TEXT:
            return fac_raw(None, reply="Ви вже з'ясували два варіанти. Що для вас зараз найважливіше далі?")
        return fac_raw("phase_1_frame_options" if no < 5 else "phase_1_define_problem")

    llm = ProductLlm(router=router, facilitator=fac)
    conv = cc.converse_card(
        knowledge(tmp_path), llm, PersonLlm(), "weighted-matrix", OPENER, turns=8, switch=True
    )
    kinds = [(d["kind"], d.get("card_id"), d.get("end")) for d in conv.routing]
    assert ("end", "weighted-matrix", "not_fit") in kinds
    assert kinds[-1] == ("choose", "five-whys", None)
    assert conv.led == "five-whys"
    assert "після «давай інакше»: end — так, нове offer без картки — ні" in cc.index([conv], STAMP)


def test_switch_conversation_that_led_the_target_first_is_not_marked_another_card(tmp_path: Path) -> None:
    """Task 714 (overseer test gap): the router chooses the target weighted-matrix after its offer and leads
    it; after «Давай інакше» it chooses five-whys. «обрано іншу картку» comes from the first choose after the
    offer, so the row does not carry it."""

    cc = script("card_conversations")

    def router(no: int, text: str) -> str:
        if no == 1:
            return offer_raw("weighted-matrix", "issue-tree")
        if text.startswith("Давай"):
            return choose_raw("weighted-matrix")
        return choose_raw("five-whys")

    def fac(no: int, text: str) -> str:
        if text == cc.SWITCH_TEXT:
            return fac_raw(None, reply="Ви вже з'ясували два варіанти. Що для вас зараз найважливіше далі?")
        return fac_raw("phase_1_frame_options" if no < 5 else "phase_1_define_problem")

    llm = ProductLlm(router=router, facilitator=fac)
    conv = cc.converse_card(
        knowledge(tmp_path), llm, PersonLlm(), "weighted-matrix", OPENER, turns=8, switch=True
    )
    chosen = [d["card_id"] for d in conv.routing if d["kind"] == "choose"]
    assert chosen[0] == "weighted-matrix"
    assert chosen[-1] == "five-whys"
    row = cc.index([conv], STAMP)
    assert "обрано іншу картку" not in row
    assert "після «давай інакше»" in row
