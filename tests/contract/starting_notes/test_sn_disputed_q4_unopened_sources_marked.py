"""DISPUTED (Q4) — not sealed until the slice planner answers.

Q4: «що в кожному basis джерело зі станом не «opened» у sources.md позначено як невідкрите» — the contract
gives examples of the mark («книгу не відкривав», «лише видача») but no fixed wording, and does not say
whether the mark must stand beside that very address. Reading taken: a note whose `basis` cites an address
that `sources.md` gives as not **opened** carries, somewhere in its `basis`, one of the marks below.
"""

import re
from pathlib import Path

from thinkhow.knowledge import read_notes

ROOT = Path(__file__).resolve().parents[3]
SOURCES = ROOT / ".engine" / "artifacts" / "starting-notes" / "sources.md"
URL = re.compile(r"https?://[^\s,;)»\"']+")
STATE = re.compile(r"\*\*(opened|search|failed)[^*]*\*\*")
MARKS = (
    "не відкрив",
    "не відкрил",
    "не відкрит",
    "невідкрит",
    "лише видач",
    "лише пошук",
    "пошуком",
    "з пошуку",
)


def _clean(url: str) -> str:
    return url.rstrip(".,;:)»—")


def states() -> dict[str, str]:
    found: dict[str, str] = {}
    entries: list[str] = []
    for line in SOURCES.read_text(encoding="utf-8").splitlines():
        if line.startswith("- "):
            entries.append(line)
        elif line.startswith(" ") and entries:
            entries[-1] += " " + line.strip()
        else:
            entries.append("")
    for entry in entries:
        state = STATE.search(entry)
        if state is None:
            continue
        for url in URL.findall(entry):
            found.setdefault(_clean(url), state.group(1))
    return found


def test_q4_a_basis_citing_a_source_not_opened_marks_it_as_not_opened() -> None:
    known = states()
    assert known
    records = read_notes(ROOT / "notes")
    assert records
    unmarked = []
    for record in records:
        cited = [_clean(u) for u in URL.findall(record.basis)]
        if any(known.get(u, "opened") != "opened" for u in cited):
            if not any(mark in record.basis.lower() for mark in MARKS):
                unmarked.append(record.id)
    assert unmarked == []
