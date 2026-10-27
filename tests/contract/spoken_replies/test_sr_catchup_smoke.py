"""Catch-up contract tests of spoken-replies: the smoke script (slice tester).

Written from the contract (.engine/slices/spoken-replies.md, «Exit criterion», the Smoke line), not from the
code of `scripts/smoke_test_spoken_replies.py`. The script is run in-process (sr_catchup_smoke_run); the
clean run is shared by the tests that read it; each «fails when» test changes ONE thing — an answer of the
real app to a `/reply`, or the form the app receives — checks that the change really happened, and expects
the smoke to fail.
"""

from __future__ import annotations

from sr_catchup_smoke_run import ANSWERED, Run, Sabotage, app_served, clean_run, run_smoke

TRUTHY = ("true", "1", "yes", "on")


def _fails(run: Run, what: str) -> None:
    app_served(run)
    assert run.rewritten > 0, f"the change ({what}) never happened, so it was not live\n" + run.out
    assert not run.ok, f"the smoke passed with {what}\n" + run.out


# --- the clean run ------------------------------------------------------------------------------------------


def test_smoke_passes_in_process_through_create_app_without_a_server_process() -> None:
    run = clean_run()
    assert run.ok, run.out
    app_served(run)
    uvicorn = [cmd for cmd in run.launches if any("uvicorn" in part for part in cmd)]
    assert not uvicorn, f"the smoke launched a real uvicorn: {uvicorn}"


def test_smoke_deps_come_from_build_deps_in_local_mode_with_its_own_facilitate() -> None:
    run = clean_run()
    app_served(run)
    local = [
        deps for environ, deps in run.built if environ.get("THINKHOW_LOCAL", "").strip().lower() in TRUTHY
    ]
    assert local, (
        f"build_deps was never called in local mode: {[env.get('THINKHOW_LOCAL') for env, _ in run.built]}"
    )
    served = run.apps[-1]
    assert any(served.storage is deps.storage for deps in local), (
        "the deps given to create_app are not those build_deps made in local mode"
    )
    assert all(served.facilitate is not deps.facilitate for deps in local), (
        "create_app got build_deps' own facilitate, not one the smoke built with a recorded model"
    )


def test_smoke_posts_reply_with_spoken_1_and_without_both_answered_200_sse() -> None:
    run = clean_run()
    app_served(run)
    spoken = [r for r in run.replies() if r.spoken == ["1"]]
    plain = [r for r in run.replies() if r.spoken != ["1"]]
    assert spoken, f"no POST …/reply with spoken=1: {[r.fields for r in run.replies()]}"
    assert plain, f"no POST …/reply without spoken=1: {[r.fields for r in run.replies()]}"
    for request in (spoken[0], plain[0]):
        assert request.status == 200, (request.fields, request.status)
        assert ANSWERED in request.body, (request.fields, request.body[:400])


# --- the smoke's own checks: one change at a time -----------------------------------------------------------


def test_smoke_fails_when_the_spoken_reply_is_not_200() -> None:
    _fails(run_smoke(Sabotage(answer_for="spoken", new_status=500)), "/reply with spoken=1 answered 500")


def test_smoke_fails_when_the_plain_reply_is_not_200() -> None:
    _fails(run_smoke(Sabotage(answer_for="plain", new_status=500)), "/reply without spoken=1 answered 500")


def test_smoke_fails_when_the_spoken_reply_has_no_answered_event() -> None:
    _fails(
        run_smoke(Sabotage(answer_for="spoken", blank_answered=True)),
        "the SSE of /reply with spoken=1 without the event answered",
    )


def test_smoke_fails_when_the_plain_reply_has_no_answered_event() -> None:
    _fails(
        run_smoke(Sabotage(answer_for="plain", blank_answered=True)),
        "the SSE of /reply without spoken=1 without the event answered",
    )


def test_smoke_fails_when_the_section_is_missing_with_spoken_1() -> None:
    run = run_smoke(Sabotage(hide_spoken=True))
    assert any(r.spoken == ["1"] for r in run.replies()), "the smoke sent no spoken=1 to hide\n" + run.out
    _fails(run, "the app never receiving spoken (so no system holds «# Людина слухає»)")


def test_smoke_fails_when_the_section_is_present_without_spoken_1() -> None:
    _fails(
        run_smoke(Sabotage(force_spoken=True)),
        "the app receiving spoken=1 on every /reply (so the plain reply's system holds the section)",
    )
