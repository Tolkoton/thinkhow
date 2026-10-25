"""Disputed (Q1): `resolve_link` keeps the Google link on any `Exception`, but a `BaseException` that is not
an `Exception` (KeyboardInterrupt) passes up (slice tester; held until the slice planner answers)."""

import pytest
from rd_fakes import GOOGLE, HeadRecorder

from thinkhow.platform.links import resolve_link


def test_q1_resolve_link_lets_a_base_exception_that_is_not_an_exception_pass() -> None:
    with pytest.raises(KeyboardInterrupt):
        resolve_link(GOOGLE + "AUZ", HeadRecorder(KeyboardInterrupt()))
