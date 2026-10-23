"""Disputed contract test of skel-learning (Q2): `analyze_failed` names the class, not the message.

Not sealed until the slice planner answers Q2: «клас винятку; без тексту» — read here as «without the
exception's text» as well as without the conversation's.

Corrected by objection (round 2, slice continuous-analysis, task 202): the topic needs no closing.
"""

from datetime import timedelta
from pathlib import Path

import pytest
from skell_fakes import ALICE, NOW, S1, FakeLlm, LogCapture, S, T, install_log_capture, write_topic

from thinkhow.learning.analyze import analyze
from thinkhow.platform.llm import LlmUnavailable
from thinkhow.platform.storage import LocalStorage

H = timedelta(hours=1)


@pytest.fixture
def logs(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> LogCapture:
    return install_log_capture(monkeypatch, capsys)


def test_q2_analyze_failed_line_has_no_exception_message(tmp_path: Path, logs: LogCapture) -> None:
    storage = LocalStorage(tmp_path)
    write_topic(
        storage,
        ALICE,
        "t-a00000000001",
        [S(1, [T(1, "user", "План.", NOW - 3 * H), T(2, "model", "Так?", NOW - 3 * H + S1)])],
    )
    analyze(storage, FakeLlm(fail={"План.": LlmUnavailable("повідомлення-винятку-q2")}), NOW)
    failed = logs.events("analyze_failed")
    assert len(failed) == 1
    assert "LlmUnavailable" in [v for v in failed[0].values() if isinstance(v, str)]
    assert "повідомлення-винятку-q2" not in logs.raw()
