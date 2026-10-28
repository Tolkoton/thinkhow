"""Block tests of one-conversation (slice tester, mode `block`).

The slice stands alone: no feature artifact names it, so it is one block and the work is closed with it. The
tests follow the contract `.engine/slices/one-conversation.md` — the four measurable items of «Goal», the
«Exit criterion», and the one connection inside the block that the contract names (Q2: the analyzer's context
goes after the history the facilitator gets) — and the public signatures, not the bodies.

The person's turns go the way a person sends them: through the web app (`POST …/reply`, `POST …/retry`) with
an injected clock; the nightly run is the real `analyze` on the same storage. Helpers are the sealed ones of
earlier slices (`ca_fakes` of continuous-analysis, `oc_fakes` of one-conversation), reused as they are.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import cast

from fastapi.testclient import TestClient

HERE = Path(__file__).resolve().parent
for sibling in ("one_conversation", "continuous_analysis"):
    path = str(HERE.parent / sibling)
    if path not in sys.path:
        sys.path.insert(0, path)

from oc_fakes import Fac, T, ca  # noqa: E402

from thinkhow.learning.analyze import AnalyzeReport, analyze  # noqa: E402
from thinkhow.platform.config import load_settings  # noqa: E402
from thinkhow.platform.identity import IapIdentity  # noqa: E402
from thinkhow.platform.llm import Llm  # noqa: E402
from thinkhow.platform.speech import ScriptedSpeech  # noqa: E402
from thinkhow.platform.storage import LocalStorage  # noqa: E402
from thinkhow.web.server import Deps, create_app  # noqa: E402
from thinkhow.workspace import TopicRef, set_language  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
ALICE = ca.ALICE
CTX, NEW = ca.CTX, ca.NEW
DAY, H, M = ca.DAY, ca.H, ca.M
H_ALICE = ca.H_ALICE


class Clock:
    """The app's `now`; the test moves it."""

    def __init__(self, at: datetime) -> None:
        self.at = at

    def __call__(self) -> datetime:
        return self.at


def web(tmp_path: Path, storage: LocalStorage, fac: Fac, now: Callable[[], datetime]) -> TestClient:
    """The web app over `storage`, Alice signed in, the facilitator double `fac`."""
    set_language(storage, ALICE, "uk-UA")
    settings = load_settings(
        {
            "THINKHOW_LOCAL": "true",
            "THINKHOW_LOCAL_DIR": str(tmp_path),
            "THINKHOW_OWNER_EMAIL": "owner@example.com",
        }
    )
    deps = Deps(
        storage=storage,
        identity=IapIdentity("aud-test", lambda token, audience: ca.TOKENS[token]),
        settings=settings,
        facilitate=fac,
        now=now,
        speech=ScriptedSpeech("(локальний режим) розпізнаний текст"),
    )
    return TestClient(create_app(deps), raise_server_exceptions=False, follow_redirects=False)


def url(ref: TopicRef) -> str:
    return f"/topics/{ref.uid}/{ref.topic_id}"


def send(client: TestClient, ref: TopicRef, text: str) -> None:
    r = client.post(f"{url(ref)}/reply", data={"text": text}, headers=H_ALICE)
    assert r.status_code == 200, r.text[-500:]


def again(client: TestClient, ref: TopicRef) -> None:
    r = client.post(f"{url(ref)}/retry", headers=H_ALICE)
    assert r.status_code == 200, r.text[-500:]


def nightly(storage: LocalStorage, llm: ca.FakeLlm, now: datetime) -> AnalyzeReport:
    return analyze(storage, cast(Llm, llm), now)


# --- acceptance (1): over the web, the turn that opens a new session gets every earlier turn -----------


def test_acceptance_1_over_the_web_each_new_sessions_turn_gets_every_earlier_turn_of_the_topic(
    tmp_path: Path,
) -> None:
    storage = LocalStorage(tmp_path / "data")
    t0 = ca.NOW - 4 * DAY
    clock = Clock(t0)
    fac = Fac(["Два?", "Чотири?", "Шість?"])
    client = web(tmp_path, storage, fac, clock)
    ref = ca.new_topic(storage, ALICE, t0 - M)

    send(client, ref, "Один.")  # session 1: #1, #2
    clock.at = t0 + DAY
    send(client, ref, "Три.")  # session 2: #3, #4
    clock.at = t0 + 2 * DAY
    send(client, ref, "П'ять.")  # session 3: #5, #6

    assert [c.turn_no for c in fac.contexts] == [1, 3, 5]
    assert fac.contexts[0].history == []
    assert fac.contexts[1].history == [T("user", "Один."), T("model", "Два?")]
    assert fac.contexts[2].history == [
        T("user", "Один."),
        T("model", "Два?"),
        T("user", "Три."),
        T("model", "Чотири?"),
    ]


# --- the connection: the analyzer's context goes after the facilitator's history (Q2) ------------------


def test_connection_the_analyzers_context_is_the_history_the_facilitator_got_for_the_first_new_turn(
    tmp_path: Path,
) -> None:
    storage = LocalStorage(tmp_path / "data")
    t0 = ca.NOW - 4 * DAY
    clock = Clock(t0)
    fac = Fac(["Два?", "Чотири?", None, "Шість?"])
    client = web(tmp_path, storage, fac, clock)
    ref = ca.new_topic(storage, ALICE, t0 - M)

    send(client, ref, "Один.")  # session 1
    nightly(storage, ca.FakeLlm(), t0 + H)
    clock.at = t0 + DAY
    send(client, ref, "Три.")  # session 2
    nightly(storage, ca.FakeLlm(), t0 + DAY + H)
    assert ca.obs_names(storage, ref) == {"t1-t2.json", "t3-t4.json"}

    clock.at = t0 + 2 * DAY
    send(client, ref, "П'ять.")  # session 3: the answer fails
    clock.at = t0 + 2 * DAY + M
    again(client, ref)  # retry: #6

    retried = fac.contexts[3]
    assert retried.turn_no == 5
    assert retried.history == [
        T("user", "Один."),
        T("model", "Два?"),
        T("user", "Три."),
        T("model", "Чотири?"),
    ]

    llm = ca.FakeLlm()
    assert nightly(storage, llm, t0 + 2 * DAY + H) == AnalyzeReport(written=1, skipped=0, failed=0)
    assert len(llm.calls) == 1
    lines = llm.calls[0].lines()
    assert lines == [
        CTX,
        "#1 людина: Один.",
        "#2 фасилітатор: Два?",
        "#3 людина: Три.",
        "#4 фасилітатор: Чотири?",
        NEW,
        "#5 людина: П'ять.",
        "#6 фасилітатор: Шість?",
    ]
    # the context, turn by turn, is the history the facilitator was given for #5 — no more, no less
    who = {"user": "людина", "model": "фасилітатор"}
    shown = lines[1 : lines.index(NEW)]
    assert shown == [f"#{i} {who[t.role]}: {t.text}" for i, t in enumerate(retried.history, start=1)]
    assert llm.calls[0].anchors() == ["t5", "t6"]
    assert ca.obs_names(storage, ref) == {"t1-t2.json", "t3-t4.json", "t5-t6.json"}


# --- acceptance (3): the smoke script by the command the contract names ------------------------------


def test_acceptance_3_the_smoke_script_run_by_its_own_command_prints_ok() -> None:
    uv = shutil.which("uv")
    assert uv is not None, "uv is not on PATH"
    done = subprocess.run(
        [uv, "run", "python", "scripts/smoke_test_one_conversation.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=300,
        env={k: v for k, v in os.environ.items() if k != "PYTHONPATH"},
    )
    assert done.returncode == 0, done.stdout[-2000:] + done.stderr[-2000:]
    assert any(line.startswith("OK: ") for line in done.stdout.splitlines()), done.stdout[-2000:]


# --- acceptance (4): ruff, mypy, lint-imports green (the full pytest is the run this test is part of) ---


def test_acceptance_4_ruff_mypy_and_lint_imports_are_green() -> None:
    uv = shutil.which("uv")
    assert uv is not None, "uv is not on PATH"
    env = dict(os.environ)
    commands = {
        "ruff": ([uv, "run", "ruff", "check", "."], env),
        "mypy": ([uv, "run", "mypy", "src", "tests"], env),
        "lint-imports": ([uv, "run", "lint-imports"], {**env, "PYTHONPATH": "src"}),
    }
    failed = []
    for name, (command, environ) in commands.items():
        done = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=600, env=environ)
        if done.returncode != 0:
            failed.append(f"{name} (exit {done.returncode}):\n{(done.stdout + done.stderr)[-1500:]}")
    assert not failed, "\n\n".join(failed)
