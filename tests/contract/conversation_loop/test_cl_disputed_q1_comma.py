"""Disputed (Q1): the cut comma ends the left piece. Not sealed until Q1."""

from cloop_fakes import HERE, run_node_test

FILE = HERE / "cl_disputed_q1_comma.test.mjs"


def test_piece_cut_at_a_comma_ends_with_it() -> None:
    run_node_test(FILE, "a piece cut at a comma ends with that comma")
