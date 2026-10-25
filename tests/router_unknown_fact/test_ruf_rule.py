"""Slice router-unknown-fact (builder's test): the rule «не знає факту про світ → answer» in its place."""

from thinkhow.facilitation.route import ROUTER_RULES

RULE = (
    "- Якщо людина каже, що не знає чогось про світ, що можна дізнатися з інтернету (ринок, ціни, строки, "
    'як це зазвичай роблять інші), або питає, як це дізнатися, — "answer": система знайде це сама, і людину '
    "не треба вести способом думати, щоб вона гадала. Факти про саму людину (її гроші, досвід, бажання) — "
    'не "answer".'
)
ASK_RULE = '- В "ask" не питай людину фактів про світ, які можна знайти: для них є "answer".'
LANGUAGE_RULE = "- Відповідай мовою людини за правилом нижче."


def flat(text: str) -> str:
    return " ".join(text.split())


def test_the_rule_stands_right_after_the_ask_rule_under_the_rules_and_before_the_language_rule() -> None:
    rules = flat(ROUTER_RULES)
    assert flat(RULE) in rules
    at = rules.index(flat(RULE))
    assert rules.index("Правила:") < rules.index(ASK_RULE) < at < rules.index(LANGUAGE_RULE)
    assert rules.index(ASK_RULE) + len(ASK_RULE) + 1 == at
