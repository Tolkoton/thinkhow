"""Task 306: «не знаю» about what only reality shows leads to an assumption and a cheap test, not a question.

In the topic t-84d1517cb1c1 the owner said three times that they did not know (#5 the result to aim at, #11
the customers' pains, #15 which pain matters most) and each time the system asked again. These tests hold
the rule in the text the facilitator's model gets under the router: the unknown goes into the map as an
assumption, the system offers a starting hypothesis with its reason and moves to the card's riskiest-
assumption and cheapest-test phases when the card has them, else to a cheap test as the person's step; a
goal or a number she has nothing to base on gets a starting value with its reason, as a question.
"""

from pathlib import Path

from thinkhow.facilitation.respond import RESEARCH_SECTION, system_instruction
from thinkhow.knowledge import current, seed
from thinkhow.platform.storage import LocalStorage

CARDS = Path(__file__).resolve().parents[3] / "cards"


def flat(text: str) -> str:
    return " ".join(text.split())


def test_what_only_reality_shows_is_not_asked_again() -> None:
    research = flat(RESEARCH_SECTION)
    assert "не питай людину вдруге" in research
    for example in ("як відреагують клієнти", "яка біль для них головна", "чи хтось купить"):
        assert example in research, example


def test_the_unknown_goes_into_the_map_as_an_assumption() -> None:
    assert "пунктом типу «assumption»" in flat(RESEARCH_SECTION)


def test_a_starting_hypothesis_with_its_reason_stays_her_choice() -> None:
    research = flat(RESEARCH_SECTION)
    assert "Запропонуй стартову гіпотезу з причиною" in research
    assert "Гіпотеза — твоя пропозиція: у карту її не пиши, доки людина її не прийме" in research


def test_it_moves_to_the_cards_assumption_and_test_phases_or_a_cheap_test() -> None:
    research = flat(RESEARCH_SECTION)
    assert "фази найризикованішого припущення і найдешевшого тесту" in research
    assert "не проходячи фаз, які питають те, чого людина не знає" in research
    assert (
        "запропонуй дешевий тест як її крок: що зробити, за який строк і яке число скаже «так» чи «ні»"
        in (research)
    )


def test_a_goal_or_number_without_ground_gets_a_starting_value() -> None:
    research = flat(RESEARCH_SECTION)
    assert "нема на що спертися" in research
    assert "запропонуй стартове значення з причиною як питання" in research


def test_the_opportunity_tree_has_the_phases_the_rule_names(tmp_path: Path) -> None:
    """The card the router offered on #1 carries both phases, and the routed instruction carries the rule."""
    storage = LocalStorage(tmp_path)
    seed(storage, CARDS)
    card = current(storage).cards["opportunity-tree"]
    titles = [phase.title for phase in card.facilitator.phases]
    assert "Найризикованіше припущення" in titles
    assert "Найдешевший тест" in titles
    assert RESEARCH_SECTION in system_instruction(card, (), "uk-UA", routed=True)
