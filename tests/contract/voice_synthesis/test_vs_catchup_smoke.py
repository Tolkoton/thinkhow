"""Catch-up contract tests of voice-synthesis: the smoke script (slice tester).

Written from the contract (.engine/slices/voice-synthesis.md, «Exit criterion», the Smoke line), not from the
code. The script is run in-process from the repository root with the server's launch watched
(vs_catchup_smoke_run); each «fails when» test changes ONE answer of the real server and expects the smoke
to fail. The answers are picked by method, status and body, so the order of the smoke's steps is not
assumed.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from vs_catchup_smoke_run import APP, rewrite, rule, run_smoke, server_ran

# --- the whole run ------------------------------------------------------------------------------------


def test_smoke_passes_against_the_real_server_in_local_mode(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    run = run_smoke(monkeypatch, tmp_path)
    assert run.ok, run.out
    server_ran(run)
    launch = run.launches[0]
    assert any(part == "uvicorn" or part.endswith("/uvicorn") for part in launch.cmd), launch.cmd
    assert APP in launch.cmd, launch.cmd
    assert launch.environ.get("THINKHOW_LOCAL", "").strip().lower() in ("true", "1", "yes"), (
        launch.environ.get("THINKHOW_LOCAL")
    )


# --- the smoke's own checks: one broken answer at a time ------------------------------------------------


def test_smoke_fails_when_the_uk_topic_page_lacks_data_voice_yes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    run = run_smoke(
        monkeypatch, tmp_path, rewrite(rule("GET", 200, has=b'data-voice="yes"', replace=b'data-voice="yes"'))
    )
    server_ran(run)
    assert not run.ok, 'a uk-UA topic page without data-voice="yes" was not caught'


def test_smoke_fails_when_speak_for_uk_is_not_200(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    run = run_smoke(monkeypatch, tmp_path, rewrite(rule("POST", 200, path="/speak", new_status=502)))
    server_ran(run)
    assert not run.ok, "POST /speak for uk-UA → 502 was not caught"


def test_smoke_fails_when_speak_for_uk_is_not_audio_mpeg(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    run = run_smoke(
        monkeypatch,
        tmp_path,
        rewrite(rule("POST", 200, path="/speak", content_type="application/octet-stream")),
    )
    server_ran(run)
    assert not run.ok, "POST /speak → 200 with Content-Type application/octet-stream was not caught"


def test_smoke_fails_when_speak_bytes_are_not_silence_mp3(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    run = run_smoke(monkeypatch, tmp_path, rewrite(rule("POST", 200, path="/speak", garble=True)))
    server_ran(run)
    assert not run.ok, (
        "POST /speak → 200 audio/mpeg with bytes other than silence.mp3 (same length) was not caught"
    )


def test_smoke_fails_when_the_kk_topic_page_lacks_data_voice_no(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    run = run_smoke(
        monkeypatch, tmp_path, rewrite(rule("GET", 200, has=b'data-voice="no"', replace=b'data-voice="no"'))
    )
    server_ran(run)
    assert not run.ok, 'a kk-KZ topic page without data-voice="no" was not caught'


def test_smoke_fails_when_speak_for_kk_is_not_409(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    run = run_smoke(monkeypatch, tmp_path, rewrite(rule("POST", 409, path="/speak", new_status=200)))
    server_ran(run)
    assert not run.ok, "POST /speak for kk-KZ → 200 instead of 409 was not caught"
