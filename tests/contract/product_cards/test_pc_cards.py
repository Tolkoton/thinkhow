"""Contract tests of product-cards: the 7 new cards in the real `cards/` (Goal 1, Seam «Content», Hardest
seams 3 and 6, the router seeing 25 cards). Slice tester; written from the contract, not the code."""

from pathlib import Path

from pc_helpers import (
    ALL_IDS,
    CARDS,
    NEW_IDS,
    OLD_IDS,
    card_file,
    leading_comment,
    load,
    normalise,
    old_text,
    strings,
)

from thinkhow.facilitation.route import router_instruction
from thinkhow.knowledge import Card, card_prompt, current, seed
from thinkhow.platform.storage import LocalStorage

# Seam 6: one row per new card, written by hand from the slice «Seam (contract)».
TABLE = {
    "customer-interviews": ("The Mom Test (Fitzpatrick)", "§3.1", "практик"),
    "demand-test": ("Pretotyping і гіпотеза XYZ (Savoia)", "§3.2", "рандомізован"),
    "positioning": ("Positioning (Dunford)", "§3.3", "практик"),
    "offer-design": ("Value Equation (Hormozi)", "§3.4", "без досліджень"),
    "value-pricing": ("Economic Value to the Customer (EVC)", "§3.5", "практик"),
    "traction-channels": ("Bullseye (Traction)", "§3.6", "практик"),
    "unit-economics": ("Unit economics (LTV і CAC)", "§3.7", "арифметик"),
}

# Seam 3: the phrase that names each neighbour, and the pairs (both sides of each).
PHRASE = {
    "jobs-to-be-done": "наймають",
    "opportunity-tree": "дерево можливостей",
    "customer-interviews": "розмови з клієнтами",
    "demand-test": "перевірка попиту",
    "offer-design": "офер",
    "value-pricing": "ціна від цінності",
    "positioning": "позиціонування",
    "traction-channels": "канали",
}
PAIRS = [
    ("customer-interviews", "jobs-to-be-done"),
    ("demand-test", "opportunity-tree"),
    ("offer-design", "value-pricing"),
    ("offer-design", "positioning"),
    ("value-pricing", "positioning"),
    ("traction-channels", "demand-test"),
]


def test_cards_holds_exactly_25_files_the_18_ids_of_task_302_and_the_7_new() -> None:
    assert sorted(p.name for p in CARDS.iterdir() if p.is_file()) == sorted(f"{c}.yaml" for c in ALL_IDS)


def test_every_new_card_is_valid_its_id_is_its_file_name_and_card_prompt_renders_it() -> None:
    for cid in NEW_IDS:
        card = Card.model_validate(load(cid))
        assert card.id == cid
        assert card_prompt(card).strip(), cid


def test_seam6_method_of_each_new_card_is_the_seam_line_word_for_word() -> None:
    for cid, (method, _, _) in TABLE.items():
        assert load(cid)["method"] == method, cid


def test_seam6_the_top_comment_of_each_new_card_names_its_section_of_research_04() -> None:
    for cid, (_, section, _) in TABLE.items():
        comment = leading_comment(cid)
        assert comment, f"{cid}: no comment at the top"
        assert section in comment, (cid, section, comment)


def test_seam6_purpose_names_the_strength_of_the_evidence() -> None:
    for cid, (_, _, mark) in TABLE.items():
        purpose = load(cid)["facilitator"]["purpose"]
        assert mark in purpose.lower(), (cid, mark, purpose)


def test_seam6_interviews_pricing_and_demand_test_say_hypothetical_buy_or_pay_is_inflated() -> None:
    for cid in ("customer-interviews", "value-pricing", "demand-test"):
        text = " ".join(strings(load(cid)["facilitator"])).lower()
        assert "гіпотетичн" in text or "купив би" in text or "заплатив би" in text, cid


def test_seam6_offer_design_has_the_guards_of_research_04_s3_4() -> None:
    data = load("offer-design")
    end = " ".join(strings(data["facilitator"]["phases"][-1]) + [data["facilitator"]["ending"]]).lower()
    assert "гіпотез" in end, "offer-design: «гіпотез» not in the last phase or ending"
    assert "перевір" in end, "offer-design: «перевір» not in the last phase or ending"
    text = " ".join(strings(data)).lower()
    assert "дефіцит" in text
    assert "гаранті" in text


def _names_neighbour(when_no: list[str], phrase: str) -> bool:
    norm = normalise()
    return any(norm(phrase) in norm(item) for item in when_no)


def test_seam3_when_no_of_both_sides_of_each_pair_names_the_neighbour() -> None:
    # the rule itself: a when_no without the neighbour's phrase fails it, one with it passes
    assert not _names_neighbour(["Людина вже знає клієнтів і хоче інше."], PHRASE["value-pricing"])
    assert _names_neighbour(["Треба порахувати «Ціна від цінності» для клієнта."], PHRASE["value-pricing"])
    for a, b in PAIRS:
        for side, neighbour in ((a, b), (b, a)):
            when_no = load(side)["router"]["when_no"]
            assert _names_neighbour(when_no, PHRASE[neighbour]), (side, neighbour, PHRASE[neighbour])


def test_other_old_cards_are_byte_for_byte_the_files_of_6091f88() -> None:
    for cid in OLD_IDS:
        if cid in ("jobs-to-be-done", "opportunity-tree"):
            continue
        assert card_file(cid).read_text(encoding="utf-8") == old_text(f"cards/{cid}.yaml"), cid


def test_the_router_sees_all_25_cards_seeded_from_cards_dir(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    seed(store, CARDS)
    knowledge = current(store)
    assert sorted(knowledge.cards) == sorted(ALL_IDS)
    text = router_instruction(knowledge, "uk")
    for cid in ALL_IDS:
        assert f"### {cid} — " in text, cid
