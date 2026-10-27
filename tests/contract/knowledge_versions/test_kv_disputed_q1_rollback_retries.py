"""Disputed contract test of knowledge-versions (question Q1): how many times a rollback retries the number.
Reading taken: «спробувати наступний номер, до 3 разів» counts the retries after the first attempt, so a
rollback makes at most 4 attempts. Slice tester; written from the contract, not the code."""

from collections.abc import Callable
from pathlib import Path

import pytest
from kv_fakes import NOW, ROLLBACKS, RecordingStorage, apply_ok, mpath, rec, seeded

from thinkhow.knowledge import KnowledgeConflict, rollback


def rival_taking(times: int, other: int) -> tuple[list[str], Callable[[RecordingStorage, str], None]]:
    taken: list[str] = []

    def rival(s: RecordingStorage, path: str) -> None:
        if len(taken) < times:
            taken.append(path)
            n = int(path.removeprefix(ROLLBACKS).removesuffix(".json"))
            s.put(
                path,
                {
                    "n": n,
                    "rev": other,
                    "reverts": {"m2": mpath("m2", 1)},
                    "restore": {"m2": None},
                    "changed": ["m2"],
                    "at": NOW.isoformat(),
                    "by": "rival",
                },
            )

    return taken, rival


def test_rollback_wins_on_the_third_retry_and_gives_up_after_it(tmp_path: Path) -> None:
    store = seeded(tmp_path / "wins")
    other = apply_ok(store, [rec("m2")])
    r = apply_ok(store, [rec("m3")])
    taken, rival = rival_taking(3, other)
    store.rival = rival
    assert rollback(store, r, "owner", NOW) == 4
    assert len(taken) == 3

    store = seeded(tmp_path / "gives-up")
    other = apply_ok(store, [rec("m2")])
    r = apply_ok(store, [rec("m3")])
    taken, rival = rival_taking(4, other)
    store.rival = rival
    with pytest.raises(KnowledgeConflict):
        rollback(store, r, "owner", NOW)
    assert len(taken) == 4
