"""Contract tests of conversation-resilience: createEarcons(ctx) under `node --test`."""

from cr_fakes import HERE, run_node_test

FILE = HERE / "cr_earcons.test.mjs"


def test_earcons_listening_one_quiet_tone_of_about_880_hz_for_about_120_ms_through_a_ga() -> None:
    run_node_test(
        FILE,
        "listening: one quiet tone of about 880 Hz for about 120 ms through a GainNode of the same context",
    )


def test_earcons_tick_a_very_quiet_tone_of_about_660_hz_for_about_60_ms_through_a_gainn() -> None:
    run_node_test(
        FILE, "tick: a very quiet tone of about 660 Hz for about 60 ms through a GainNode of the same context"
    )


def test_earcons_error_two_tones_going_down_about_440_then_about_330_hz_about_300_ms_to() -> None:
    run_node_test(FILE, "error: two tones going down, about 440 then about 330 Hz, about 300 ms together")
