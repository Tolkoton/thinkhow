"""Contract tests of voice-dictation, Seam 5: createRecorder of conversation.js under `node --test`."""

from vd_fakes import HERE, run_node_test

FILE = HERE / "vd_recorder.test.mjs"


def test_seam5_start_asks_audio_picks_the_first_supported_type_at_64_kbit() -> None:
    run_node_test(FILE, "start: audio only, the first supported type, 64 kbit/s, ui.recording")


def test_seam5_stop_gathers_the_blob_after_the_stop_event_and_posts_it_with_its_type() -> None:
    run_node_test(FILE, "stop: the Blob is gathered after the stop event and posted with its type")


def test_seam5_empty_recorder_mime_type_gives_audio_webm() -> None:
    run_node_test(FILE, "stop: an empty recorder.mimeType gives a Blob of type audio/webm")


def test_seam5_limit_timer_is_set_and_cleared_by_the_button() -> None:
    run_node_test(FILE, "limit: start sets a limitMs timer, the button's stop clears it")


def test_seam5_limit_timer_stops_by_itself_then_a_press_is_one_stop_one_post() -> None:
    run_node_test(
        FILE,
        "limit: the timer stops by itself; a press after it gives one recorder.stop and one POST",
    )


def test_seam5_microphone_denied_shows_its_message_state_as_before() -> None:
    run_node_test(FILE, "denied: the microphone refused shows its message and leaves the state as before")


def test_seam5_200_with_text_inserts_it_then_idle() -> None:
    run_node_test(FILE, "200 with text: insertText(text), then idle")


def test_seam5_502_shows_fragment_offers_and_recognize_resends_the_same_recording() -> None:
    run_node_test(
        FILE,
        "502: the fragment's text, offerRecognize; recognize() sends the same recording; then 200",
    )


def test_seam5_200_with_empty_text_is_not_heard_and_keeps_the_recording() -> None:
    run_node_test(FILE, "200 with empty text: «Не почули слів», offerRecognize, the recording stays")


def test_seam5_network_error_and_non_json_answers_show_the_network_message() -> None:
    run_node_test(FILE, "network error and a 200 page that is not JSON: the network message, offerRecognize")


def test_seam5_in_flight_recognizing_until_the_answer() -> None:
    run_node_test(
        FILE,
        "in flight: ui.recognizing is the last call until the answer; every answer is followed by more",
    )


def test_seam5_after_a_refusal_a_new_recording_replaces_the_held_one() -> None:
    run_node_test(FILE, "after a refusal a new recording replaces the held one")
