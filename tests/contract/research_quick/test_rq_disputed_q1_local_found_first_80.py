"""Disputed (Q1): `local_found` cuts the person's turn to its first 80 characters, exactly
`text[:80]`, without stripping or an ellipsis (slice tester; held until the slice planner answers)."""

from rq_fakes import PREMORTEM

from thinkhow.facilitation.respond import answer_schema
from thinkhow.platform.llm import Found, Source, Turn
from thinkhow.web.local import local_found

LONG = (
    "Не знаю, скільки коштує оренда офісу в Лейпцигу біля вокзалу, "
    "і чи є там парковка для клієнтів та персоналу"
)
FIRST_80 = "Не знаю, скільки коштує оренда офісу в Лейпцигу біля вокзалу, і чи є там парковк"


def test_q1_local_found_query_is_the_first_80_characters_of_the_turn() -> None:
    assert len(LONG) > 80 and len(FIRST_80) == 80 and LONG.startswith(FIRST_80)
    frame = '[Карта проблеми зараз]\n{"items":[],"phase_id":null,"last_turn":0}\n\n'
    frame += f"[Репліка людини #1]\n{LONG}"
    got = local_found("system", [Turn("user", frame)], answer_schema(PREMORTEM))
    assert got == Found((FIRST_80,), (Source("example.org", "https://example.org/local-search"),), None)
