"""Contract tests of conversation-resilience: the invariants I1-I4 under `node --test`."""

from cr_fakes import HERE, run_node_test

FILE = HERE / "cr_invariants.test.mjs"


def test_I1_no_speak_request_carries_text_of_a_line_or_an_http_address_for_any_spl() -> None:
    run_node_test(
        FILE,
        "I1: no /speak request carries text of a «Джерела:» line or "
        "an http address, for any split into deltas",
    )


def test_I2_one_human_turn_gets_at_most_one_automatic_retry_whatever_the_failures() -> None:
    run_node_test(
        FILE,
        "I2: one human turn gets at most one automatic /retry, "
        "whatever the failures; the next turn has its own",
    )


def test_I3_no_recognition_error_fewer_than_three_in_a_row_and_no_voice_error_turn() -> None:
    run_node_test(
        FILE, "I3: no recognition error (fewer than three in a row) and no voice error turns the mode off"
    )


def test_I4_the_voice_text_only_grows_by_appending_and_the_pieces_sent_to_speak_gi() -> None:
    run_node_test(
        FILE,
        "I4: the voice text only grows by appending, and the pieces "
        "sent to /speak give voiceText of the attempt",
    )
