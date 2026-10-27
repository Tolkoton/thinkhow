"""Contract tests of conversation-loop, Seam 1: createSilenceDetector under `node --test`."""

from cloop_fakes import HERE, run_node_test

FILE = HERE / "cl_detector.test.mjs"


def test_speech_200ms_then_1600ms_quiet_ends_at_the_last_speech_frame() -> None:
    run_node_test(FILE, "speech 200 ms then 1600 ms of quiet: speech-end with at = the last speech frame")


def test_click_of_100ms_gives_no_event() -> None:
    run_node_test(FILE, "a click of 100 ms gives no event")


def test_steady_car_noise_is_calibrated_away() -> None:
    run_node_test(
        FILE,
        "steady car noise from the first frame after reset is calibrated away; speech on top starts and ends",
    )


def test_speech_inside_calibration_then_speech_start() -> None:
    run_node_test(
        FILE,
        "speech 200 ms after reset (inside calibration, noise 0.01): none inside, then speech-start",
    )


def test_pause_of_1000ms_is_not_the_end() -> None:
    run_node_test(FILE, "a pause of 1000 ms in the middle of speech is not the end")


def test_sound_longer_than_max_ms_gives_speech_end() -> None:
    run_node_test(
        FILE, "sound without a break longer than maxMs (default 870000) gives speech-end with at = t"
    )


def test_calibration_takes_the_minimum() -> None:
    run_node_test(
        FILE,
        "calibration takes the minimum, not the mean: a person speaking at once does not raise the threshold",
    )


def test_threshold_is_max_of_start_level_and_three_times_noise() -> None:
    run_node_test(FILE, "the threshold is max(startLevel, 3 × noise level)")


def test_noise_follows_quiet_frames_by_moving_average() -> None:
    run_node_test(FILE, "the noise level follows quiet frames by the moving average 0.95/0.05")


def test_candidates_and_speech_do_not_change_the_noise() -> None:
    run_node_test(
        FILE, "candidate frames shorter than startMs and speech frames do not change the noise level"
    )


def test_after_speech_end_waits_for_speech_start_again() -> None:
    run_node_test(FILE, "after speech-end the detector waits for speech-start again")


def test_reset_forgets_everything() -> None:
    run_node_test(FILE, "reset forgets everything, the noise level and the speech in progress included")
