"""Contract tests of deep-research-confirm-first: the prompt texts the contract fixes word for word —
`research.md` and `deep_field.md` (one consent to the research, Q11) (slice tester; from the contract)."""

from pathlib import Path

from dc_fakes import flat

FACILITATION = Path(__file__).resolve().parents[3] / "src" / "thinkhow" / "facilitation"

RESEARCH_DEEP_SENTENCE = (
    "Коли питання багатогранне (ринок, кілька шляхів, порівняння) і швидкого пошуку замало, "
    "скажи одним реченням, що це можна дослідити глибше, якщо людина захоче; "
    "згоди не питай — що саме шукати, покаже система."
)
RESEARCH_LAST_LINE = "Пункт «fact» — лише для знайденого пошуком; що людина розповіла про себе — не «fact»."
OLD_RESEARCH_SENTENCE = (
    "Коли питання багатогранне (ринок, кілька шляхів, порівняння) і швидкого пошуку замало, запропонуй "
    "людині глибоке дослідження: скажи, що це займе близько двох хвилин, і спитай, чи шукати."
)
DEEP_FIELD_BODY = (
    "Коли людина сама просить дослідити глибоко або погоджується на глибше дослідження, "
    "про яке щойно сказано, — постав питання дослідження в deep_question "
    "(одне речення: що саме з'ясувати), а в reply не кажи, що починаєш, і не питай згоди: "
    "система сама допише, що саме досліджуватиме, і спитає людину. Інакше deep_question — null."
)


def test_research_md_says_in_one_sentence_it_can_research_deeper_without_asking_consent() -> None:
    text = flat((FACILITATION / "research.md").read_text(encoding="utf-8"))
    sentence = flat(RESEARCH_DEEP_SENTENCE)
    assert sentence in text
    assert text.index(sentence) < text.index(flat(RESEARCH_LAST_LINE))
    assert flat(OLD_RESEARCH_SENTENCE) not in text


def test_deep_field_md_body_tells_the_model_not_to_announce_the_start_nor_ask_consent() -> None:
    text = flat((FACILITATION / "deep_field.md").read_text(encoding="utf-8"))
    assert text.endswith(flat(DEEP_FIELD_BODY))
