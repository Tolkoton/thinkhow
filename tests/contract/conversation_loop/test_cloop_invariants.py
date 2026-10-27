"""Contract tests of conversation-loop: the invariants I1-I3 under `node --test`."""

from cloop_fakes import HERE, run_node_test

FILE = HERE / "cl_invariants.test.mjs"


def test_I1_no_recording_or_voice_while_thinking_or_speaking() -> None:
    run_node_test(
        FILE, "I1: while thinking or speaking no level from the microphone starts a recording or sends /voice"
    )


def test_I2_no_speak_request_over_1000_bytes() -> None:
    run_node_test(FILE, "I2: no /speak request carries text over 1000 bytes of UTF-8")


def test_I3_pieces_joined_give_the_input_text() -> None:
    run_node_test(
        FILE, "I3: the pieces joined by a space give the input text, up to spaces, for any split into deltas"
    )
