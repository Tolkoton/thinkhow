"""Contract tests of conversation-resilience: voiceText and stableText under `node --test`."""

from cr_fakes import HERE, run_node_test

FILE = HERE / "cr_text.test.mjs"


def test_voicetext_drops_the_sources_line_at_the_end_of_the_answer() -> None:
    run_node_test(FILE, "voiceText drops the sources line at the end of the answer")


def test_voicetext_drops_a_sources_line_in_the_middle_up_to_the_next_blank_line() -> None:
    run_node_test(
        FILE, "voiceText drops a sources line in the middle up to the next blank line and keeps what follows"
    )


def test_voicetext_turns_every_markdown_link_into_its_name_whatever_the_address() -> None:
    run_node_test(FILE, "voiceText turns every Markdown link into its name, whatever the address")


def test_voicetext_drops_a_bare_http_address_up_to_the_space() -> None:
    run_node_test(FILE, "voiceText drops a bare http address up to the space")


def test_stabletext_cuts_the_unfinished_word_everything_after_the_last_space_or() -> None:
    run_node_test(FILE, "stableText cuts the unfinished word: everything after the last space or line break")


def test_stabletext_holds_an_unclosed_link_a_without_after_it_or_without_its_cl() -> None:
    run_node_test(
        FILE, "stableText holds an unclosed link: a [ without ] after it, or ]( without its closing )"
    )


def test_stabletext_does_not_hold_1_without_a_after_it() -> None:
    run_node_test(FILE, "stableText does not hold [1] without a ( after it")


def test_stabletext_cuts_a_beginning_of_the_sources_literal_standing_at_the_ver() -> None:
    run_node_test(FILE, "stableText cuts a beginning of the sources literal standing at the very end")


def test_stabletext_cuts_an_open_sources_line_at_the_end_from_its_literal() -> None:
    run_node_test(FILE, "stableText cuts an open sources line at the end from its literal")


def test_stabletext_applies_its_cuts_round_and_round_until_the_text_stops_getti() -> None:
    run_node_test(FILE, "stableText applies its cuts round and round until the text stops getting shorter")
