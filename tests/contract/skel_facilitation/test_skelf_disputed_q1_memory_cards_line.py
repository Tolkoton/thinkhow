"""Disputed (Q1): the «Картки:» line of a memory record, exactly as in sketches/gemini-eu/context/memory.md.

Reading taken: `Картки: <id>, <id>.` — ids joined by «, » and closed with a period, as every PoC line is.
Not sealed until the slice planner answers Q1.
"""

from skelf_fakes import MEMORY, ScenarioLlm, answer, collect, context, knowledge

from thinkhow.facilitation import respond
from thinkhow.knowledge import MemoryRecord

# Since notes-readers Q1 card alpha's instruction holds only the records that name alpha, so the
# one-card line is checked on a record that names alpha (objection under notes-readers, owner's
# answer A, task 724).
OWN_ONE_CARD = MemoryRecord(
    id="M-3",
    title="Свій досвід",
    cards=["alpha"],
    noticed="людина пропускає фазу",
    do="назвати фазу ще раз",
    basis="2 сесії.",
)


def test_memory_cards_line_is_ids_joined_by_comma_space_with_a_period() -> None:
    fake = ScenarioLlm(deltas=["Що?"], done_raw=answer("Що?", "a_one"))
    collect(lambda: respond(context(), knowledge(memory=[*MEMORY, OWN_ONE_CARD]), fake))
    lines = fake.stream_calls[0].system.splitlines()
    at = lines.index("### M-1 — Перший досвід")
    assert lines[at + 1] == "Картки: alpha, beta."
    assert lines[lines.index("### M-3 — Свій досвід") + 1] == "Картки: alpha."
    assert "### M-2 — Чужий досвід" not in lines
