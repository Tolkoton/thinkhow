"""The injections of the version check (learning-loop S1): the person-details check, the size measure.

`vet_with(llm)` asks the model once whether the memory records carry details of particular people; `measure`
is the length of the longest instruction a reader builds from the Knowledge. Does NOT write anything.
"""

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from thinkhow.facilitation.respond import system_instruction
from thinkhow.facilitation.route import router_instruction
from thinkhow.knowledge import CurrentKnowledge, MemoryRecord
from thinkhow.knowledge.versions import Vet
from thinkhow.platform.llm import Llm, Turn

VETTER = """Ти перевіряєш нотатки до методів мислення ThinkHow, перш ніж їх прочитають ведучі розмов
з іншими людьми. Нотатка має бути узагальненим досвідом: коли метод допомагає, де застрягають, як вести.
У ній не має бути подробиць конкретних людей: імен, міст, назв їхніх компаній, їхніх сум, дат і подій їхнього
життя, цитат з їхніх розмов. Назви методів, авторів і джерел методу — не подробиці людей.
ok — true, якщо жодна нотатка не має таких подробиць; інакше false, і reason — коротко, що і де."""


class VetAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    reason: str


def vet_with(llm: Llm) -> Vet:
    """The check as a function of the records: one generate_json; the model's errors pass through."""

    def vet(records: Sequence[MemoryRecord]) -> str | None:
        answer = llm.generate_json(VETTER, [Turn("user", _records_text(records))], VetAnswer, None)
        return None if answer.ok else answer.reason

    return vet


def _records_text(records: Sequence[MemoryRecord]) -> str:
    return "\n\n".join(
        f"### {r.id} — {r.title}\nЩо помітили: {r.noticed}\nЩо робити: {r.do}\nПідстава: {r.basis}"
        for r in records
    )


def measure(knowledge: CurrentKnowledge) -> int:
    """The longest of the router's instruction and every card's facilitator instruction (under the router)."""
    facilitator = (
        len(system_instruction(card, knowledge.memory, None, True)) for card in knowledge.cards.values()
    )
    return max(len(router_instruction(knowledge, None)), *facilitator)
