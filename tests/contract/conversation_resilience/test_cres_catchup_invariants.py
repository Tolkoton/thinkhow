"""Catch-up contract tests of conversation-resilience: the invariants I1-I4 under `node --test`, on inputs of
their own (slice tester; see cres_catchup_invariants.test.mjs)."""

from cr_fakes import HERE, run_node_test

FILE = HERE / "cres_catchup_invariants.test.mjs"


def test_I1_no_speak_text_holds_a_sources_line_or_an_http_address_links_with_spaces_and_a_retry() -> None:
    run_node_test(
        FILE,
        "catch-up I1: no /speak text holds a «Джерела:» line or an http address, "
        "links with spaces, http:// and a retry",
    )


def test_I2_at_most_one_automatic_retry_per_human_turn_409_a_retry_that_worked_a_new_start() -> None:
    run_node_test(
        FILE,
        "catch-up I2: at most one automatic /retry per human turn, a 409, "
        "a retry that worked, and a new start after off",
    )


def test_I3_recognition_errors_fewer_than_three_in_a_row_and_every_voice_error_keep_the_mode_on() -> None:
    run_node_test(
        FILE,
        "catch-up I3: recognition errors (400, network, empty, 504) fewer than three in a row "
        "and every voice error keep the mode on",
    )


def test_I4_the_voice_text_grows_only_by_appending_and_the_pieces_give_voicetext_of_the_attempt() -> None:
    run_node_test(
        FILE,
        "catch-up I4: the voice text grows only by appending, "
        "and the pieces sent to /speak give voiceText of the attempt",
    )
