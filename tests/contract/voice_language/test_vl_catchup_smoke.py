"""Catch-up contract tests of voice-language: the smoke script (slice tester).

Written from the contract (.engine/slices/voice-language.md, «Exit criterion»), not from the code. The script
runs in-process (runpy, as `__main__`) from the repository root, with `subprocess.Popen` watched: the launch
of `uvicorn thinkhow.web.app:app` is recorded (command, environment, working folder) and a folder of this test
is put first on the server's `PYTHONPATH`. Its `sitecustomize.py` always leaves a mark (the server really ran
it) and, for a «fails when» test, breaks one fact inside the server, so the smoke's own checks are judged by
what it does when the server misbehaves. The breakages are chosen so that they do not depend on the order of
the smoke's steps.

The smoke writes `.engine/artifacts/spikes/voice-language-smoke-<дата>.txt` into the repository; every run
here restores those files afterwards, so the builder's record is left as it was.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from vl_catchup_smoke_run import APP, OTHER_EMAIL, RU_WRITES_FIRST, repo_files, rewrite, run_smoke, server_ran

# --- the whole run ------------------------------------------------------------------------------------


def test_smoke_passes_the_first_visit_language_choice_and_ru_refusal(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    run = run_smoke(monkeypatch, tmp_path)
    assert run.ok, run.out
    server_ran(run)


def test_smoke_runs_real_uvicorn_in_local_mode_as_the_default_person(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    run = run_smoke(monkeypatch, tmp_path)
    assert run.ok, run.out
    server_ran(run)
    launch = run.launches[0]
    assert any(part == "uvicorn" or part.endswith("/uvicorn") for part in launch.cmd), launch.cmd
    assert APP in launch.cmd, launch.cmd
    assert launch.environ.get("THINKHOW_LOCAL", "").strip().lower() == "true"
    assert launch.environ.get("THINKHOW_LOCAL_USER_ID", "local-owner") == "local-owner"
    assert launch.environ.get("THINKHOW_LOCAL_USER_EMAIL", "owner@localhost") == "owner@localhost"


def test_smoke_works_in_a_temporary_folder_not_in_the_repository(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    before = repo_files()
    run = run_smoke(monkeypatch, tmp_path)
    assert run.ok, run.out
    server_ran(run)
    local_dir = Path(run.launches[0].environ["THINKHOW_LOCAL_DIR"])
    if not local_dir.is_absolute():
        local_dir = run.launches[0].cwd / local_dir
    assert local_dir.resolve().is_relative_to((tmp_path / "temp").resolve()), local_dir
    assert repo_files() - before == set()  # the smoke's own record is removed or restored by run_smoke


# --- the smoke's own checks: one broken fact at a time --------------------------------------------------


@pytest.mark.parametrize("nth", [1, 2], ids=["first_redirect", "second_redirect"])
def test_smoke_fails_when_home_without_a_language_does_not_redirect(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, nth: int
) -> None:
    run = run_smoke(monkeypatch, tmp_path, rewrite(("GET", "/", 303, nth, 200, b"", None)))
    server_ran(run)
    assert not run.ok, f"GET / without a language answered 200 (redirect #{nth}) and it was not caught"


def test_smoke_fails_when_home_redirects_elsewhere(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    run = run_smoke(monkeypatch, tmp_path, rewrite(("GET", "/", 303, 0, None, b"", "/elsewhere")))
    server_ran(run)
    assert not run.ok, "GET / → 303 with Location /elsewhere was not caught"


def test_smoke_fails_when_the_language_page_is_not_200(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    run = run_smoke(monkeypatch, tmp_path, rewrite(("GET", "/language", 200, 0, 500, b"", None)))
    server_ran(run)
    assert not run.ok, "GET /language → 500 was not caught"


def test_smoke_fails_when_the_language_page_has_no_select_code(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    run = run_smoke(monkeypatch, tmp_path, rewrite(("GET", "/language", 200, 0, None, b'name="code"', None)))
    server_ran(run)
    assert not run.ok, 'a language page without <select name="code"> was not caught'


def test_smoke_fails_when_choosing_pl_PL_does_not_answer_303(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    run = run_smoke(monkeypatch, tmp_path, rewrite(("POST", "/language", 303, 0, 200, b"", None)))
    server_ran(run)
    assert not run.ok, "POST /language code=pl-PL → 200 was not caught"


def test_smoke_fails_when_home_does_not_show_polski(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    run = run_smoke(monkeypatch, tmp_path, rewrite(("GET", "/", 200, 0, None, b"Polski", None)))
    server_ran(run)
    assert not run.ok, "a home page without «Мова: Polski» was not caught"


def test_smoke_fails_when_the_profile_has_another_email(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    run = run_smoke(monkeypatch, tmp_path, OTHER_EMAIL)
    server_ran(run)
    assert not run.ok, (
        'profile.json other than {"email": "owner@localhost", "language": "pl-PL"} was not caught'
    )


def test_smoke_fails_when_ru_RU_is_not_400(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    run = run_smoke(monkeypatch, tmp_path, rewrite(("POST", "/language", 400, 0, 200, b"", None)))
    server_ran(run)
    assert not run.ok, "POST /language code=ru-RU → 200 was not caught"


def test_smoke_fails_when_refused_ru_RU_changed_the_profile(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    run = run_smoke(monkeypatch, tmp_path, RU_WRITES_FIRST)
    server_ran(run)
    assert not run.ok, "a profile changed by the refused POST code=ru-RU was not caught"
