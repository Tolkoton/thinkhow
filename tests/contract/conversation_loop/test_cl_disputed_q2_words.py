"""Disputed (Q2): I3 read word by word. Not sealed until Q2."""

from cloop_fakes import HERE, run_node_test

FILE = HERE / "cl_disputed_q2_words.test.mjs"


def test_pieces_keep_every_word_apart() -> None:
    run_node_test(FILE, "the pieces joined by a space keep every word apart, deltas cut right after a space")
