"""Catch-up contract tests of conversation-resilience: the smoke script (slice tester).

Written from the contract (.engine/slices/conversation-resilience.md, «Exit criterion», the Smoke line, and
«Hardest seams», Seam 6), not from the code of `scripts/smoke_test_conversation_resilience.py`. Each run is
the exit criterion's command (see `cres_catchup_run`). The clean run is shared by the tests that read it; each
«fails when» test breaks ONE thing the smoke must notice — answers of the real server, or the page (a script
put before the real `conversation.js`) — and checks that the breakage really happened before it expects the
smoke to fail.
"""

from __future__ import annotations

from pathlib import Path

from cres_catchup_run import APP, NO_WAKE_LOCK_JS, OSC_200_JS, Run, clean_run, rule, run_smoke, server_ran

TRUTHY = ("true", "1", "yes", "on", "t", "y")


def _fails(run: Run, what: str) -> None:
    server_ran(run)
    assert run.code != 0, f"the smoke passed with {what}\n" + run.out


# --- the clean run ------------------------------------------------------------------------------------------


def test_smoke_passes_on_the_talk_harness_stand_in_local_mode() -> None:
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


def test_smoke_writes_its_output_to_the_artifact_itself() -> None:
    run = clean_run()
    server_ran(run)
    assert run.smoke_txt is not None, "the smoke wrote no .engine/artifacts/conversation-resilience/smoke.txt"
    assert run.smoke_txt.strip(), "smoke.txt is empty"


# --- the smoke's own checks: one breakage at a time -------------------------------------------------------


def test_smoke_fails_when_the_third_cycle_never_gets_an_answer(tmp_path: Path) -> None:
    html = '<p class="error">CRCU: /reply зламано</p>'
    run = run_smoke(
        tmp_path,
        rules=[rule("reply", start=3, status=502, html=html), rule("retry", status=502, html=html)],
    )
    assert any(r["seg"] == "reply" and r["n"] >= 3 for r in run.kind("rewritten")), (
        "the third /reply never came, so the breakage was not live\n" + run.out
    )
    _fails(run, "the third /reply and its automatic /retry answered 502 (the mode stops after 2 cycles)")


def test_smoke_fails_when_every_speak_fails_not_just_one(tmp_path: Path) -> None:
    run = run_smoke(tmp_path, rules=[rule("speak", status=502, html='<p class="error">CRCU: голос</p>')])
    seen = run.page_speak()
    assert seen and all(status != "200" for status in seen.values()), (
        f"a /speak still answered 200, so the breakage was not live: {seen}\n" + run.out
    )
    _fails(run, "every /speak answered 502 (200 fewer than requests by all of them, not by one)")


def test_smoke_fails_when_the_page_never_asks_for_the_wake_lock(tmp_path: Path) -> None:
    run = run_smoke(tmp_path, breakage=NO_WAKE_LOCK_JS)
    assert run.beacons("wakelock-gone") > 0, (
        "navigator.wakeLock could not be taken away from the page, so the breakage was not live\n" + run.out
    )
    assert not run.beacons_starting("wakelock-screen"), "the page still called navigator.wakeLock.request"
    _fails(run, 'no navigator.wakeLock on the page (request("screen") never called)')


def test_smoke_fails_when_no_oscillator_sounds_at_about_880_hz(tmp_path: Path) -> None:
    run = run_smoke(tmp_path, breakage=OSC_200_JS)
    assert run.beacons("osc-pinned") > 0, (
        "the page created no oscillator to pin, so the breakage was not live\n" + run.out
    )
    _fails(run, "every oscillator of the page at 200 Hz (no ~880 Hz listening tone)")
