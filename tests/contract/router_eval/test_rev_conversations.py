"""Contract tests of `scripts/card_conversations.py`, the driver of a conversation (Seam 5) and the synthetic
person's instruction (Seam 4): a conversation through the product's `workspace.reply` in a temporary local
storage, with a fake product model and a fake person (slice router-eval; slice tester, from the contract)."""

import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from rev_fakes import (
    CARDS,
    CASES,
    OWNER,
    STAMP,
    Down,
    PersonLlm,
    ProductLlm,
    ask_raw,
    choose_raw,
    fac_raw,
    knowledge,
    live_detector,
    offer_raw,
    script,
)

from thinkhow.facilitation import Candidate, Decision, Profile, Rev
from thinkhow.knowledge import CurrentKnowledge

OPENER = "Чому в нас падає кількість реєстрацій? Уже місяць менше, і я не розумію, звідки це."


def cc() -> Any:
    return script("card_conversations")


@pytest.fixture
def k(tmp_path: Path) -> CurrentKnowledge:
    return knowledge(tmp_path / "knowledge")


def d_offer(turn: int, *ids: str) -> dict[str, Any]:
    profile = Profile.model_validate(
        {
            "intent": "find_cause",
            "structuredness": "moderately_structured",
            "reversibility": "two_way_door",
            "stakes": "medium",
            "data": "qualitative_only",
            "options": "unclear",
            "emotion": "neutral_analytical",
            "social": "product_or_team",
        }
    )
    d = Decision(
        turn=turn,
        rev=Rev(rev=1, n=18),
        kind="offer",
        profile=profile,
        candidates=[Candidate(card_id=i, why=f"Це допоможе ({i}).") for i in ids],
        card_id=None,
        end=None,
        why="пропоную за профілем",
    )
    return d.model_dump(mode="json")


# --- choice_text --------------------------------------------------------------------------------------------


def test_target_first_in_the_last_offer_is_davai_pershe() -> None:
    assert cc().choice_text([d_offer(1, "five-whys", "issue-tree")], "five-whys") == "Давай перше."


def test_target_second_or_third_is_davai_with_its_number_counted_from_one() -> None:
    assert cc().choice_text([d_offer(1, "issue-tree", "five-whys")], "five-whys") == "Давай 2."
    assert cc().choice_text([d_offer(1, "issue-tree", "scamper", "five-whys")], "five-whys") == "Давай 3."


def test_the_place_is_read_from_the_last_offer() -> None:
    decisions = [d_offer(1, "five-whys", "issue-tree"), d_offer(3, "scamper", "five-whys")]
    assert cc().choice_text(decisions, "five-whys") == "Давай 2."


# --- the person's instruction (Seam 4) ----------------------------------------------------------------------


def test_person_instruction_names_no_method_for_the_situation_of_every_card() -> None:
    names_a_method = live_detector()
    cases = yaml.safe_load(CASES.read_text("utf-8"))["cases"]
    ids = sorted(yaml.safe_load(f.read_text("utf-8"))["id"] for f in CARDS.glob("*.yaml"))
    for cid in ids:
        situation = next(c["text"] for c in cases if c["kind"] == "positive" and c["expect"] == cid)
        text = cc().person_instruction(situation, "Коли тобі пропонують кілька способів, обери один номером.")
        assert isinstance(text, str) and text
        assert not names_a_method(text), cid


# --- the driver (Seam 5) ------------------------------------------------------------------------------------


def test_target_offered_second_the_person_writes_davai_2(k: CurrentKnowledge) -> None:
    def router(no: int, text: str) -> str:
        if text.startswith("Давай"):
            return choose_raw("weighted-matrix")
        return offer_raw("weighted-matrix", "five-whys")

    plan = {2: fac_raw("phase_1_frame_options"), 3: fac_raw("phase_4_table_gut_check", True)}
    llm = ProductLlm(
        router=router, facilitator=lambda no, text: plan.get(no, fac_raw("phase_1_frame_options"))
    )
    cc().converse_card(k, llm, PersonLlm(), "five-whys", OPENER, turns=12)
    assert llm.person_turns()[1] == OPENER
    assert llm.person_turns()[2] == "Давай 2."


def test_another_card_chosen_index_names_it_and_the_card_led_is_judged(k: CurrentKnowledge) -> None:
    def router(no: int, text: str) -> str:
        if text.startswith("Давай"):
            return choose_raw("weighted-matrix")
        return offer_raw("weighted-matrix", "five-whys")

    plan = {2: fac_raw("phase_1_frame_options"), 3: fac_raw("phase_4_table_gut_check", True)}
    llm = ProductLlm(
        router=router, facilitator=lambda no, text: plan.get(no, fac_raw("phase_1_frame_options"))
    )
    conv = cc().converse_card(k, llm, PersonLlm(), "five-whys", OPENER, turns=12)
    assert conv.target == "five-whys"
    assert conv.led == "weighted-matrix"
    assert conv.offered is True
    assert conv.done is True
    assert conv.last_phase is True
    assert "обрано іншу картку (weighted-matrix)" in cc().index([conv], STAMP)


def test_the_loop_stops_on_the_end_of_the_card_actually_led(k: CurrentKnowledge) -> None:
    def router(no: int, text: str) -> str:
        if text.startswith("Давай"):
            return choose_raw("weighted-matrix")
        return offer_raw("weighted-matrix", "five-whys")

    plan = {2: fac_raw("phase_1_frame_options"), 3: fac_raw("phase_4_table_gut_check", True)}
    llm = ProductLlm(
        router=router, facilitator=lambda no, text: plan.get(no, fac_raw("phase_1_frame_options"))
    )
    person = PersonLlm(replies=["Ми порівнюємо дві причини, і мені важко."])
    cc().converse_card(k, llm, person, "five-whys", OPENER, turns=12)
    assert sorted(llm.person_turns()) == [1, 2, 3]
    assert llm.person_turns()[3] == "Ми порівнюємо дві причини, і мені важко."
    assert len(person.calls) == 1


def test_the_loop_stops_after_n_turns_of_the_person_without_an_end(k: CurrentKnowledge) -> None:
    def router(no: int, text: str) -> str:
        if text.startswith("Давай"):
            return choose_raw("five-whys")
        return offer_raw("five-whys", "issue-tree")

    llm = ProductLlm(router=router, facilitator=lambda no, text: fac_raw("phase_1_define_problem"))
    cc().converse_card(k, llm, PersonLlm(), "five-whys", OPENER, turns=5)
    n = len(llm.person_turns())
    assert 5 <= n <= 7, sorted(llm.person_turns())


def test_target_not_offered_the_person_takes_the_first_and_offered_is_false(k: CurrentKnowledge) -> None:
    def router(no: int, text: str) -> str:
        if text.startswith("Давай"):
            return choose_raw("issue-tree")
        return offer_raw("issue-tree", "scamper")

    plan = {2: fac_raw("phase_1_root_question"), 3: fac_raw("phase_4_deepen_and_next", True)}
    llm = ProductLlm(
        router=router, facilitator=lambda no, text: plan.get(no, fac_raw("phase_1_root_question"))
    )
    conv = cc().converse_card(k, llm, PersonLlm(), "five-whys", OPENER, turns=12)
    assert llm.person_turns()[2] == "Давай перше."
    assert conv.offered is False
    assert conv.led == "issue-tree"


def test_switch_the_third_turn_after_choose_is_the_switch_text(k: CurrentKnowledge) -> None:
    def router(no: int, text: str) -> str:
        if text.startswith("Давай") and text != cc().SWITCH_TEXT:
            return choose_raw("weighted-matrix")
        if no == 1:
            return offer_raw("weighted-matrix", "five-whys")
        return offer_raw("five-whys", "issue-tree")

    def fac(no: int, text: str) -> str:
        if text == cc().SWITCH_TEXT:
            return fac_raw(None, reply="Ви вже з'ясували два варіанти. Що для вас зараз найважливіше далі?")
        return fac_raw("phase_1_frame_options" if no < 4 else "phase_2_criteria")

    llm = ProductLlm(router=router, facilitator=fac)
    conv = cc().converse_card(k, llm, PersonLlm(), "weighted-matrix", OPENER, turns=8, switch=True)
    turns = llm.person_turns()
    assert turns[2] == "Давай перше."
    assert turns[5] == cc().SWITCH_TEXT
    assert [n for n, t in turns.items() if t == cc().SWITCH_TEXT] == [5]
    kinds = [(d["kind"], d.get("card_id"), d.get("end")) for d in conv.routing]
    at_end = kinds.index(("end", "weighted-matrix", "not_fit"))
    later_offers = [d for d in conv.routing[at_end + 1 :] if d["kind"] == "offer"]
    assert later_offers
    assert "weighted-matrix" not in [c["card_id"] for c in later_offers[0]["candidates"]]


def test_switch_after_the_card_ended_says_the_card_ended_before_the_switch(k: CurrentKnowledge) -> None:
    def router(no: int, text: str) -> str:
        if text.startswith("Давай"):
            return choose_raw("weighted-matrix")
        return offer_raw("weighted-matrix", "five-whys")

    plan = {2: fac_raw("phase_1_frame_options"), 3: fac_raw("phase_4_table_gut_check", True)}
    llm = ProductLlm(
        router=router, facilitator=lambda no, text: plan.get(no, fac_raw("phase_1_frame_options"))
    )
    conv = cc().converse_card(k, llm, PersonLlm(), "weighted-matrix", OPENER, turns=8, switch=True)
    assert cc().SWITCH_TEXT not in llm.person_turns().values()
    assert "картка закінчилась до перемикання" in cc().index([conv], STAMP)


def test_failed_is_retried_twice_through_workspace_retry_then_broken(k: CurrentKnowledge) -> None:
    def router(no: int, text: str) -> str:
        if text.startswith("Давай"):
            return choose_raw("five-whys")
        return offer_raw("five-whys", "issue-tree")

    def fac(no: int, text: str) -> str:
        raise Down("the stream broke")

    llm = ProductLlm(router=router, facilitator=fac)
    person = PersonLlm()
    conv = cc().converse_card(k, llm, person, "five-whys", OPENER, turns=12)
    assert len(llm.stream_calls) == 3
    assert {c.index for c in llm.stream_calls} == {2}
    assert person.calls == []
    assert "обірвано: Down" in cc().index([conv], STAMP)


def test_seeded_choice_leads_the_card_from_the_first_turn_without_the_router(k: CurrentKnowledge) -> None:
    title = yaml.safe_load((CARDS / "five-whys.yaml").read_text("utf-8"))["title"]
    plan = {1: fac_raw("phase_1_define_problem"), 2: fac_raw("phase_3_reverse_check_and_change", True)}
    llm = ProductLlm(
        router=lambda no, text: ask_raw(),
        facilitator=lambda no, text: plan.get(no, fac_raw("phase_1_define_problem")),
    )
    conv = cc().converse_card(k, llm, PersonLlm(), "five-whys", OPENER, turns=12, seeded=True)
    assert llm.calls[0].kind == "stream"
    assert llm.calls[0].turn_no == 1
    assert title in llm.calls[0].system
    first_two = [(d["kind"], d["turn"]) for d in conv.routing[:2]]
    assert first_two == [("offer", 0), ("choose", 0)]
    assert conv.routing[1]["card_id"] == "five-whys"
    assert conv.seeded is True
    assert conv.led == "five-whys"
    assert "вели без вибору роутером" in cc().index([conv], STAMP)


def test_owner_topic_starts_with_his_turn_1_verbatim(k: CurrentKnowledge) -> None:
    first = json.loads(OWNER.read_text("utf-8"))["person_turns"][0]
    llm = ProductLlm(router=lambda no, text: ask_raw())
    cc().converse_owner(k, llm, PersonLlm(), turns=3)
    assert " ".join(llm.person_turns()[1].split()) == " ".join(first.split())
