"""Overseer test gap (board 717): /reply non-200 with a fragment while the mode is on."""

from cloop_fakes import HERE, run_node_test

FILE = HERE / "cl_gap_reply_error.test.mjs"


def test_reply_409_in_the_mode_shows_its_text_and_enables_the_controls() -> None:
    run_node_test(
        FILE, "/reply 409 in the mode: its text in #error, the mode off, no reload, #mic and #send enabled"
    )
