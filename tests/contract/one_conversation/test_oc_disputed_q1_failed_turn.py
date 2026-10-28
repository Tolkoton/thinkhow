"""Disputed (Q1): `turn` of `reply_failed` is the number of the person's turn being answered (`n`),
not the number the failed answer would have had. Slice tester; from the contract, not the code."""

from pathlib import Path

import pytest
from oc_fakes import Fac, ask_reply, ca

from thinkhow.platform.storage import LocalStorage
from thinkhow.workspace import Failed

ALICE = ca.ALICE


@pytest.fixture
def logs(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> ca.LogCapture:
    return ca.install_log_capture(monkeypatch, capsys)


def test_q1_reply_failed_turn_is_the_persons_turn_number(tmp_path: Path, logs: ca.LogCapture) -> None:
    storage = LocalStorage(tmp_path)
    t0 = ca.NOW - 3 * ca.DAY
    ref = ca.new_topic(storage, ALICE, t0 - ca.M)
    fac = Fac(["Два?", "Чотири?", None])
    ask_reply(storage, fac, ALICE, ref, "Один.", t0)
    ask_reply(storage, fac, ALICE, ref, "Три.", t0 + ca.DAY)
    got = ask_reply(storage, fac, ALICE, ref, "П'ять.", t0 + ca.DAY + ca.M)
    assert isinstance(got[-1], Failed)
    (line,) = logs.events("reply_failed")
    assert line["turn"] == 5
