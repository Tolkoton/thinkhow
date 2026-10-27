"""Contract tests of conversation-loop, Seam 2: splitSentences under `node --test`."""

from cloop_fakes import HERE, run_node_test

FILE = HERE / "cl_split.test.mjs"


def test_sentence_ends_on_a_mark_followed_by_a_space() -> None:
    run_node_test(FILE, "a sentence ends on . ! ? … followed by a space; the unfinished tail goes to rest")


def test_newline_followed_by_newline_ends_a_sentence() -> None:
    run_node_test(
        FILE, "a newline followed by a newline ends a sentence; so does a mark followed by a newline"
    )


def test_mark_not_followed_by_space_does_not_end() -> None:
    run_node_test(FILE, "a mark not followed by a space or newline does not end a sentence")


def test_mark_at_the_end_ends_only_with_final() -> None:
    run_node_test(
        FILE, "without final a mark at the very end of the text does not end the sentence; with final it does"
    )


def test_final_tail_goes_and_rest_is_empty() -> None:
    run_node_test(FILE, "with final the tail without a mark goes too and rest is empty")


def test_blank_sentences_dropped_edges_trimmed() -> None:
    run_node_test(FILE, "sentences of spaces only are dropped and the edges are trimmed")


def test_long_cyrillic_sentence_cut_at_the_last_comma() -> None:
    run_node_test(
        FILE,
        "a sentence of 2500 bytes of Cyrillic is cut into pieces of at most 1000 bytes at the last comma",
    )


def test_long_sentence_without_comma_cut_at_the_last_space() -> None:
    run_node_test(
        FILE,
        "no comma: cut at the last space before the limit; the final tail is cut too",
    )


def test_long_run_without_space_cut_at_a_character_boundary() -> None:
    run_node_test(FILE, "a long run without a space is cut at a character boundary")
