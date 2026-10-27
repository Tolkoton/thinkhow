"""DISPUTED (Q2) — not sealed until the slice planner answers.

Q2: «жодного нового → нічого; лог `notes_published` (rev або None, кількість)» — when nothing is new, is the
line `notes_published` with `rev` None still logged, or is nothing logged at all? Reading taken: it is logged.
"""

from pathlib import Path

import pytest
from sn_fakes import Job, events, facilitator, router


def test_q2_a_run_with_nothing_new_logs_notes_published_with_rev_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    jb = Job(tmp_path, monkeypatch)
    jb.seed()
    jb.put("alpha.yaml", [router("alpha"), facilitator("alpha")])
    assert jb("notes") == 0
    capsys.readouterr()
    assert jb("notes") == 0
    published = events(capsys.readouterr().out, "notes_published")
    assert len(published) == 1
    assert "rev" in published[0] and published[0]["rev"] is None
