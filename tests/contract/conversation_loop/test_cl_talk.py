"""Contract tests of conversation-loop, Seam 3 and the page: createTalk through attach under `node --test`."""

from cloop_fakes import HERE, run_node_test

FILE = HERE / "cl_talk.test.mjs"


def test_attach_shows_talk_only_on_a_voice_page_with_audio() -> None:
    run_node_test(FILE, "attach shows #talk only with data-voice=yes, AudioContext and mediaDevices")


def test_start_sets_up_audio_listening_and_a_recorder() -> None:
    run_node_test(
        FILE,
        "start: AudioContext resumed, one stream, analyser 1024, a frame every 50 ms, listening, a recorder",
    )


def test_recorder_type_is_the_first_supported() -> None:
    run_node_test(FILE, "the recorder type is the first supported of audio/webm;codecs=opus, audio/mp4")


def test_refused_microphone_shows_the_error_and_stays_off() -> None:
    run_node_test(FILE, "a refused microphone: the error «Немає доступу до мікрофона.» and the state off")


def test_one_cycle_voice_reply_speak_one_at_a_time_listening() -> None:
    run_node_test(
        FILE,
        "one cycle: speech, /voice, /reply spoken=1, /speak one sentence at a time, listening",
    )


def test_marks_speech_end_and_voice_start() -> None:
    run_node_test(
        FILE,
        "marks: talk:speech-end at the last speech frame, talk:voice-start at start() of the first sentence",
    )


def test_second_turn_without_another_start() -> None:
    run_node_test(FILE, "the second turn goes the same way without another start()")


def test_each_answer_in_a_new_model_paragraph_after_its_user_turn() -> None:
    run_node_test(
        FILE,
        "each answer goes into a new turn model paragraph after the turn user paragraph of its turn in #live",
    )


def test_empty_text_listens_again_without_a_reply() -> None:
    run_node_test(FILE, "empty text from /voice: listening again with a new recorder, no reply sent")


def test_error_with_a_fragment_shows_its_text_and_stops() -> None:
    run_node_test(
        FILE,
        "an error with a fragment (/voice or /speak not 200): its text in #error, the mode stops, no reload",
    )


def test_error_without_a_fragment_shows_the_stop_text_and_stops() -> None:
    run_node_test(
        FILE,
        "an error without a fragment (failed, decodeAudioData, network): the stop text, the mode stops",
    )


def test_second_tap_stops_everything_and_reloads() -> None:
    run_node_test(FILE, "the second tap stops everything and reloads the page")


def test_mic_send_and_field_disabled_while_on() -> None:
    run_node_test(FILE, "#mic, #send and the field are disabled while the mode is on")


def test_controller_send_posts_the_fields() -> None:
    run_node_test(
        FILE, "createController: send(text, fields) posts text and the fields; send(text) posts text only"
    )


def test_ordinary_send_has_text_only_and_answered_reloads() -> None:
    run_node_test(
        FILE, "without a tap on #talk «Надіслати» sends a body with text only and answered reloads the page"
    )
