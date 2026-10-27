"""DISPUTED (Q1) — not sealed until the slice planner answers.

Q1: `what="стартові нотатки до методів: <N>"` and the count in `notes_published`: is N the number of records
the run publishes (the new ones), or the number read from the folder? Reading taken: the new ones.
"""

from pathlib import Path

import pytest
from sn_fakes import WHAT, Job, events, facilitator, newest_record, router


def test_q1_n_in_what_and_the_logged_count_are_the_new_records_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    jb = Job(tmp_path, monkeypatch)
    jb.seed()
    jb.put("alpha.yaml", [router("alpha"), facilitator("alpha")])
    jb.put("beta.yaml", [router("beta"), facilitator("beta")])
    assert jb("notes") == 0
    jb.put("gamma.yaml", [router("gamma")])
    capsys.readouterr()
    assert jb("notes") == 0
    record = newest_record(jb.storage)
    assert record.rev == 3
    assert record.what == f"{WHAT}1"
    published = events(capsys.readouterr().out, "notes_published")
    assert len(published) == 1 and published[0]["rev"] == 3
    counts = [v for k, v in published[0].items() if k not in ("rev", "event", "severity", "request_id")]
    assert 1 in counts and 5 not in counts
