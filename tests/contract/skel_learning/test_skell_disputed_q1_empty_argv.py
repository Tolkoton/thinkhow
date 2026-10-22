"""Disputed contract test of skel-learning (Q1): `run` with an empty `argv` is «інше» → usage and code 2.

Not sealed until the slice planner answers Q1: the contract names `argv[0]`, and an empty `argv` has none.
"""

from pathlib import Path

import pytest
from skell_fakes import CARDS, NOW, local_environ

from thinkhow.learning.job import run


def test_q1_run_with_no_command_prints_usage_to_stderr_and_returns_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run([], local_environ(tmp_path), CARDS, lambda: NOW) == 2
    assert capsys.readouterr().err.strip() != ""
