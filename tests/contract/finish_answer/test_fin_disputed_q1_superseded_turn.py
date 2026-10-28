"""Disputed (Q1): the `turn` of the `reply_superseded` line is the person's turn `turn_no`, not the number the
late answer would have had (`turn_no + 1`). Not sealed until the slice planner answers."""

from __future__ import annotations

from pathlib import Path

import pytest
from fin_fakes import ALICE, T0, Fac, log_lines, new_store, seed_topic, update

from thinkhow.workspace import Delta, reply, retry

ASK = "Хочу відкрити кав'ярню."


def test_reply_superseded_turn_is_the_persons_turn_no(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    store = new_store(tmp_path)
    ref = seed_topic(store, "Тема", [("Перше", "Перша відповідь")])  # the person's turn of A is 3
    a = reply(store, Fac([["А-1", "А-2", update("А-1А-2")]]), ALICE, ref, ASK, T0)
    for event in a:
        if isinstance(event, Delta):
            break
    list(retry(store, Fac([["Б", update("Б")]]), ALICE, ref, T0))
    capsys.readouterr()
    list(a)
    lines = [line for line in log_lines(capsys.readouterr().out) if line.get("event") == "reply_superseded"]
    assert len(lines) == 1
    assert lines[0]["turn"] == 3
