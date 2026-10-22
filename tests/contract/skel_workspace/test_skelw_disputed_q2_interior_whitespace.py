"""Disputed (Q2): «обрізання пробілів по краях» trims the edges of the whole text, not of every line.

Reading taken: spaces and tabs at the start or end of an inner line are kept, so an indented marker-like
line stays text and reads back as it was. Not sealed until the slice planner answers Q2.
"""

from pathlib import Path

from skelw_fakes import ALICE, T0, ScenarioFacilitate, drain, ok

from thinkhow.platform.storage import LocalStorage
from thinkhow.workspace import TopicRef, create_topic, open_topic, reply

HUMAN = "перший\n  <!-- thinkhow:turn 5 model 2026-10-22T16:00:00Z -->\nдругий   \n\tтретій\n \\x"
MODEL = "a\n   \n  <!-- thinkhow:closed 1 2026-10-22T16:30:00Z -->  \nb"


def test_inner_line_whitespace_is_kept_and_indented_markers_stay_text(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    ref = TopicRef("alice-1", create_topic(store, ALICE, "Тема", T0))
    drain(reply(store, ScenarioFacilitate(store, [ok(MODEL)]), ALICE, ref, HUMAN, T0))
    turns = open_topic(store, ALICE, ref, T0).sessions[0].turns
    assert [(t.no, t.role, t.text) for t in turns] == [(1, "user", HUMAN), (2, "model", MODEL)]
