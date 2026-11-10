"""Test gap (overseer, task 722) of `scripts/analyze_owner_conversation.py`, Seam 4 «сирий JSON кожного
прогону»: after three runs (attempts 1, 2, 3) the artifact has each attempt's section exactly once, and the
raw JSON in it is that attempt's own — attempt 1 included, after two later runs. The sealed disputed-Q1 test
runs two attempts only, so a script that keeps just one earlier section (the last or the first) passes it.
"""

import json
import re

import pytest
from aoc_fakes import PlanLlm, guard_artifact, run_main

__all__ = ["guard_artifact"]

MARKERS = {1: "ПЕРША", 2: "ДРУГА", 3: "ТРЕТЯ"}
SECTION = re.compile(r"^## Спроба (\d+)$", re.M)
RAW = re.compile(r"^### Сирий JSON\n\n```json\n(.*?)\n```$", re.M | re.S)


def sections(text: str) -> dict[int, list[str]]:
    """The attempt sections of the artifact, by number; a number written twice gets two entries."""
    starts = [(int(m.group(1)), m.start()) for m in SECTION.finditer(text)]
    found: dict[int, list[str]] = {}
    for i, (no, start) in enumerate(starts):
        end = starts[i + 1][1] if i + 1 < len(starts) else len(text)
        found.setdefault(no, []).append(text[start:end])
    return found


@pytest.mark.usefixtures("guard_artifact")
def test_three_attempts_each_keep_their_own_raw_json(monkeypatch: pytest.MonkeyPatch) -> None:
    text = ""
    for attempt, word in MARKERS.items():
        llm = PlanLlm(marker=f"СПРОБА-{word}", old_marker=f"СТАРИЙ-{word}")
        _, text = run_main(monkeypatch, llm, attempt=attempt)
    found = sections(text)
    assert {no: len(parts) for no, parts in found.items()} == {1: 1, 2: 1, 3: 1}, sorted(found)
    for attempt, word in MARKERS.items():
        raw = RAW.search(found[attempt][0])
        assert raw is not None, f"attempt {attempt}: no raw JSON"
        data = json.loads(raw.group(1))
        assert data["new"], f"attempt {attempt}: no observations of the new analyzer"
        assert all(o["finding"].startswith(f"СПРОБА-{word}-") for o in data["new"]), attempt
        assert [o["finding"] for o in data["old"]] == [f"СТАРИЙ-{word}-одне"], attempt
