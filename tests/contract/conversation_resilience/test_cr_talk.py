"""Contract tests of conversation-resilience: the page, createTalk through attach (Seams 1-5)."""

from cr_fakes import HERE, run_node_test

FILE = HERE / "cr_talk.test.mjs"


def test_a_sources_literal_that_comes_in_pieces_is_never_spoken_only_the_text_b() -> None:
    run_node_test(
        FILE, "a sources literal that comes in pieces is never spoken: only the text before it goes to /speak"
    )


def test_a_link_in_the_middle_of_the_text_sounds_by_its_name() -> None:
    run_node_test(FILE, "a link in the middle of the text sounds by its name")


def test_a_link_split_between_deltas_sounds_by_its_name_only() -> None:
    run_node_test(FILE, "a link split between deltas sounds by its name only")


def test_a_sources_line_in_the_middle_is_dropped_and_the_deep_part_after_it_is() -> None:
    run_node_test(FILE, "a sources line in the middle is dropped and the deep part after it is spoken")


def test_a_bare_address_split_in_the_middle_of_its_scheme_leaves_no_pieces_in_s() -> None:
    run_node_test(FILE, "a bare address split in the middle of its scheme leaves no pieces in /speak")


def test_1_without_a_link_sounds_before_the_answer_ends_and_the_link_split_afte() -> None:
    run_node_test(
        FILE,
        "[1] without a link sounds before the answer ends, and the link split after it sounds by its name",
    )


def test_the_listening_tone_plays_each_time_the_mode_enters_listening_the_first() -> None:
    run_node_test(
        FILE,
        "the listening tone plays each time the mode enters listening, the first time right after the tap",
    )


def test_a_failed_recognition_empty_text_502_network_plays_the_error_tone_and_l() -> None:
    run_node_test(
        FILE,
        "a failed recognition (empty text, 502, network) plays the "
        "error tone and listens again without stopping",
    )


def test_a_failed_recognition_shows_the_fragment_text_an_empty_text_shows() -> None:
    run_node_test(
        FILE,
        "a failed recognition shows the fragment text; an empty text "
        "shows «Не почули слів — спробуйте ще раз.»",
    )


def test_three_failed_recognitions_in_a_row_the_mode_goes_off_with_the_last_tex() -> None:
    run_node_test(
        FILE, "three failed recognitions in a row: the mode goes off with the last text and the error tone"
    )


def test_a_successful_recognition_between_failures_resets_the_count() -> None:
    run_node_test(FILE, "a successful recognition between failures resets the count")


def test_a_failed_answer_one_automatic_retry_with_spoken_1_a_new_model_paragrap() -> None:
    run_node_test(
        FILE,
        "a failed answer: one automatic /retry with spoken=1, a new "
        "model paragraph, no glued pieces in /speak",
    )


def test_the_retry_fails_too_an_error_on_the_screen_the_error_tone_the_mode_goe() -> None:
    run_node_test(FILE, "the retry fails too: an error on the screen, the error tone, the mode goes off")


def test_409_from_reply_is_not_retried_an_error_the_error_tone_and_the_stop() -> None:
    run_node_test(FILE, "409 from /reply is not retried: an error, the error tone and the stop")


def test_createcontroller_retry_fields_posts_the_fields_retry_posts_no_spoken_f() -> None:
    run_node_test(FILE, "createController.retry(fields) posts the fields; retry() posts no spoken field")


def test_a_sentence_whose_speak_fails_or_does_not_decode_is_skipped_silently_th() -> None:
    run_node_test(
        FILE,
        "a sentence whose /speak fails or does not decode is skipped "
        "silently; the rest sounds, then listening",
    )


def test_while_thinking_a_tick_tone_every_10_s_on_an_interval_of_its_own_cleare() -> None:
    run_node_test(
        FILE, "while thinking a tick tone every 10 s on an interval of its own, cleared when thinking ends"
    )


def test_stop_while_thinking_clears_both_the_tick_interval_and_the_frame_interv() -> None:
    run_node_test(FILE, "stop while thinking clears both the tick interval and the frame interval")


def test_start_asks_navigator_wakelock_for_the_screen_before_its_first_await_st() -> None:
    run_node_test(
        FILE, "start() asks navigator.wakeLock for the screen before its first await, still inside the tap"
    )


def test_without_the_wake_lock_api_or_when_it_refuses_the_mode_works_silently() -> None:
    run_node_test(FILE, "without the Wake Lock API, or when it refuses, the mode works silently")


def test_stop_releases_the_wake_lock() -> None:
    run_node_test(FILE, "stop() releases the wake lock")


def test_visibilitychange_to_visible_while_on_with_the_lock_released_or_missing() -> None:
    run_node_test(
        FILE, "visibilitychange to visible while on, with the lock released or missing, asks for it again"
    )


def test_the_visibilitychange_listener_is_removed_at_stop() -> None:
    run_node_test(FILE, "the visibilitychange listener is removed at stop")


def test_the_microphone_track_ends_while_listening_one_new_getusermedia_a_new_a() -> None:
    run_node_test(
        FILE,
        "the microphone track ends while listening: one new "
        "getUserMedia, a new analyser source, a new recorder",
    )


def test_the_microphone_track_ends_while_hearing_the_utterance_is_dropped_liste() -> None:
    run_node_test(
        FILE,
        "the microphone track ends while hearing: the utterance is "
        "dropped, listening again on the new stream",
    )


def test_the_microphone_track_ends_while_thinking_or_speaking_the_stream_is_rep() -> None:
    run_node_test(
        FILE,
        "the microphone track ends while thinking or speaking: the stream is replaced and the cycle goes on",
    )


def test_the_microphone_cannot_be_opened_again_and_the_mode_goes_off() -> None:
    run_node_test(
        FILE, "the microphone cannot be opened again: «Немає доступу до мікрофона.» and the mode goes off"
    )


def test_statechange_to_suspended_or_interrupted_resume_not_running_after_1_s_s() -> None:
    run_node_test(
        FILE,
        "statechange to suspended or interrupted: resume(); not running "
        "after 1 s shows #talk-resume; a tap hides it",
    )


def test_one_check_at_the_end_of_start_a_context_still_suspended_is_resumed_and() -> None:
    run_node_test(
        FILE,
        "one check at the end of start(): a context still suspended "
        "is resumed, and after 1 s #talk-resume shows",
    )
