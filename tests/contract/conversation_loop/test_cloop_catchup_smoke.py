"""Catch-up contract tests of conversation-loop: the smoke script and its stand (slice tester).

Written from the contract (.engine/slices/conversation-loop.md, «Exit criterion», the Smoke line, and
«Hardest seams», Seam 6), not from the code of `scripts/smoke_test_conversation_mode.py` or
`scripts/talk_harness.py`. Each run is the exit criterion's command (see `cloop_catchup_run`). The clean run
is shared by the tests that read it; each «fails when» test breaks ONE thing the smoke must notice — an answer
of the real server, or the page (a script put before the real `conversation.js`) — and checks that the
breakage really happened before it expects the smoke to fail.
"""

from __future__ import annotations

from pathlib import Path

from cloop_catchup_run import (
    APP,
    DROP_SPEECH_END_JS,
    EARLY_VOICE_START_JS,
    NO_MODEL_TURNS_JS,
    NO_USER_TURNS_JS,
    STRIP_SPOKEN_JS,
    Run,
    clean_run,
    rule,
    run_smoke,
    server_ran,
)

TRUTHY = ("true", "1", "yes", "on")


def _fails(run: Run, what: str) -> None:
    server_ran(run)
    assert run.code != 0, f"the smoke passed with {what}\n" + run.out


# --- the clean run ------------------------------------------------------------------------------------------


def test_smoke_passes_against_real_uvicorn_in_local_mode() -> None:
    run = clean_run()
    assert run.code == 0, run.out
    server_ran(run)
    launch = run.kind("launch")[0]
    assert any(part == "uvicorn" or part.endswith("/uvicorn") for part in launch["cmd"]), launch["cmd"]
    assert any(APP in part for part in launch["cmd"]), launch["cmd"]
    assert launch["local"].strip().lower() in TRUTHY, launch["local"]


def test_smoke_clicks_talk_exactly_once() -> None:
    run = clean_run()
    server_ran(run)
    assert run.beacons("click") + run.beacons("click-untrusted") == 1, (
        f"clicks on #talk: trusted {run.beacons('click')}, untrusted {run.beacons('click-untrusted')}"
    )
    assert run.beacons("click") == 1, "the one click on #talk was not a real (trusted) click"


def test_smoke_microphone_sends_recorded_turns_to_voice_three_times() -> None:
    run = clean_run()
    server_ran(run)
    voice = run.requests("voice")
    assert len(voice) >= 3, voice
    for request in voice[:3]:
        assert request["status"] == 200, request
        assert request["size"] > 0, f"/voice got an empty recording: {request}"
        assert request["ctype"].startswith(("audio/webm", "audio/mp4")), request


def test_smoke_drives_three_replies_each_with_spoken_1() -> None:
    run = clean_run()
    server_ran(run)
    reply = run.requests("reply")
    assert len(reply) >= 3, reply
    for request in reply:
        assert request["spoken"] == ["1"], f"/reply without spoken=1: {request}"


def test_smoke_drives_at_least_three_speak_requests() -> None:
    run = clean_run()
    server_ran(run)
    speak = run.requests("speak")
    assert len(speak) >= 3, speak
    assert all(request["status"] == 200 for request in speak), speak


# --- the smoke's own checks: one breakage at a time -------------------------------------------------------


def test_smoke_fails_when_the_second_voice_request_errors(tmp_path: Path) -> None:
    run = run_smoke(
        tmp_path, rules=[rule("voice", 2, status=502, html='<p class="error">CLCU: /voice зламано</p>')]
    )
    assert run.kind("rewritten"), "the second /voice never came, so the breakage was not live\n" + run.out
    _fails(run, "the second /voice answered 502 (the mode stops after one cycle, not 3)")


def test_smoke_fails_when_speak_audio_does_not_decode(tmp_path: Path) -> None:
    run = run_smoke(tmp_path, rules=[rule("speak", None, garble=True)])
    assert run.kind("rewritten"), "no /speak came, so the breakage was not live\n" + run.out
    _fails(run, "every /speak answered with bytes that are not MP3 (decodeAudioData cannot take them)")


def test_smoke_fails_when_replies_lack_spoken_1(tmp_path: Path) -> None:
    run = run_smoke(tmp_path, breakage=STRIP_SPOKEN_JS)
    reply = run.requests("reply")
    assert reply and all(request["spoken"] == [] for request in reply), (
        f"the page still sent spoken to /reply, so the breakage was not live: {reply}\n" + run.out
    )
    _fails(run, "/reply sent without spoken=1")


def test_smoke_fails_when_speech_end_marks_are_missing(tmp_path: Path) -> None:
    run = run_smoke(tmp_path, breakage=DROP_SPEECH_END_JS)
    assert run.beacons("dropped-speech-end") > 0, "no talk:speech-end mark was dropped\n" + run.out
    _fails(run, "no talk:speech-end mark on the page")


def test_smoke_fails_when_voice_start_precedes_its_speech_end(tmp_path: Path) -> None:
    run = run_smoke(tmp_path, breakage=EARLY_VOICE_START_JS)
    assert run.beacons("early-voice-start") > 0, "no talk:voice-start mark was moved\n" + run.out
    _fails(run, "every talk:voice-start at time 0, before its talk:speech-end")


def test_smoke_fails_when_live_holds_no_model_answers(tmp_path: Path) -> None:
    run = run_smoke(tmp_path, breakage=NO_MODEL_TURNS_JS)
    assert run.beacons("unclassed-model") > 0, "no answer paragraph appeared in #live to break\n" + run.out
    _fails(run, '#live with 3 person turns and no <p class="turn model">')


def test_smoke_fails_when_live_holds_no_person_turns(tmp_path: Path) -> None:
    run = run_smoke(tmp_path, breakage=NO_USER_TURNS_JS)
    assert run.beacons("unclassed-user") > 0, "no person's turn appeared in #live to break\n" + run.out
    _fails(run, '#live with 3 answers and no <p class="turn user">')
