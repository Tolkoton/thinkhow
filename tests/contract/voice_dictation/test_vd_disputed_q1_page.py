"""DISPUTED (Q1): the page side of the microphone — attach in conversation.js, under `node --test`.

Reading taken: the appending rule (I5) is the page's ui, observed by loading conversation.js in a browser-like
global scope and clicking #mic. Not sealed until the slice planner answers Q1.
"""

from vd_fakes import HERE, run_node_test

FILE = HERE / "vd_disputed_q1_page.test.mjs"


def test_I5_the_recognized_text_is_only_appended_to_the_field() -> None:
    run_node_test(FILE, "I5: the text is only appended to the field")


def test_q1_page_limit_is_fourteen_and_a_half_minutes() -> None:
    run_node_test(FILE, "page: the recorder's limit is 14.5 minutes")


def test_q1_mic_and_recognize_are_disabled_while_in_flight() -> None:
    run_node_test(
        FILE,
        "page: #mic and #recognize are disabled while the request is in flight, enabled after",
    )


def test_q1_mic_state_says_recording_then_recognizing() -> None:
    run_node_test(FILE, "page: #mic-state says what is happening")
