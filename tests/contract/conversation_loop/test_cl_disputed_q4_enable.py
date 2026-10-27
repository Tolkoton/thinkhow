"""Disputed (Q4): controls enabled again after an error stop. Not sealed until Q4."""

from cloop_fakes import HERE, run_node_test

FILE = HERE / "cl_disputed_q4_enable.test.mjs"


def test_controls_enabled_again_after_an_error_stop() -> None:
    run_node_test(FILE, "after the mode stopped on an error #mic, #send and the field are enabled again")
