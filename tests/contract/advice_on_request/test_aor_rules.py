"""Task 305: advice when the person asks or is stuck — what the system would choose, why, and what argues
against; the choice stays hers. Without a request and without being stuck the facilitator leads by questions.

On #17 of the owner's topic t-84d1517cb1c1 («запропонував мені рішення сам») the old rule («Якщо людина
просить прямо сказати, що робити, — … поверни їй питання») made the system refuse. These tests hold the new
rule in the text the facilitator's model gets, under the router and without it.
"""

from pathlib import Path

from thinkhow.facilitation.respond import RESEARCH_SECTION, RULES, system_instruction
from thinkhow.knowledge import current, seed
from thinkhow.platform.storage import LocalStorage

CARDS = Path(__file__).resolve().parents[3] / "cards"


def flat(text: str) -> str:
    return " ".join(text.split())


def test_the_old_refusal_is_gone() -> None:
    rules = flat(RULES)
    assert "не давай порад" not in rules
    assert "тепло поясни, що рішення її, і поверни їй питання" not in rules
    assert "не оцінка її варіантів" not in flat(RESEARCH_SECTION)


def test_advice_is_given_on_request_or_when_stuck_with_why_against_and_her_choice() -> None:
    rules = flat(RULES)
    assert "Порада — коли людина просить або застрягла." in rules
    for part in ("що обрав би ти", "чому", "що говорить проти цього вибору", "Скажи, що вибір її"):
        assert part in rules, part
    assert "двічі поспіль не може відповісти на твоє питання" in rules
    assert "Сам, без прохання, не кажи людині, що робити" in rules


def test_advice_stays_out_of_her_map() -> None:
    assert "у карту її не пиши, доки людина сама її не прийме" in flat(RULES)


def test_research_points_to_the_advice_rule(tmp_path: Path) -> None:
    assert "оцінюй лише порадою за правилом вище" in flat(RESEARCH_SECTION)
    storage = LocalStorage(tmp_path)
    seed(storage, CARDS)
    knowledge = current(storage)
    card = next(iter(knowledge.cards.values()))
    routed = system_instruction(card, (), "uk-UA", routed=True)
    assert routed.index(RULES) < routed.index(RESEARCH_SECTION)
    assert system_instruction(card, (), "uk-UA").startswith(RULES)
