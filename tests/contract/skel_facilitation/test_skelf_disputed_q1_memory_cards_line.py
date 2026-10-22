"""Disputed (Q1): the «Картки:» line of a memory record, exactly as in sketches/gemini-eu/context/memory.md.

Reading taken: `Картки: <id>, <id>.` — ids joined by «, » and closed with a period, as every PoC line is.
Not sealed until the slice planner answers Q1.
"""

from skelf_fakes import ScenarioLlm, answer, collect, context, knowledge

from thinkhow.facilitation import respond


def test_memory_cards_line_is_ids_joined_by_comma_space_with_a_period() -> None:
    fake = ScenarioLlm(deltas=["Що?"], done_raw=answer("Що?", "a_one"))
    collect(lambda: respond(context(), knowledge(), fake))
    lines = fake.stream_calls[0].system.splitlines()
    at = lines.index("### M-1 — Перший досвід")
    assert lines[at + 1] == "Картки: alpha, beta."
    assert lines[lines.index("### M-2 — Чужий досвід") + 1] == "Картки: gamma."
