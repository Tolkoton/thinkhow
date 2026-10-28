"""Contract tests of skel-learning: the Job's composition root `job.run` (slice tester; from the contract).

Corrected by objection (round 2, slice continuous-analysis, task 202): `closed_sessions` → `topic_sessions`,
`s<n>.json` → `t<first>-t<last>.json`, `session_no`/`closed_at` → `first_turn`/`last_turn`; the topics need
no closing. `learning/job.py` itself is unchanged by that slice.

Carried over by objection (task 720, answer A) to analysis-rules: the file is an
`ObservationSet`; the local script answers one `progress` observation on the first value of the enum.
"""

from datetime import timedelta
from pathlib import Path

import pytest
from skell_fakes import (
    ALICE,
    BOB,
    CARDS,
    NOW,
    S1,
    LogCapture,
    S,
    T,
    install_log_capture,
    local_environ,
    observation_bytes,
    range_path,
    write_topic,
)

from thinkhow.learning.job import run
from thinkhow.learning.observations import Observation, ObservationSet
from thinkhow.platform.config import ConfigError
from thinkhow.platform.storage import LocalStorage
from thinkhow.workspace import TopicRef, topic_sessions

H = timedelta(hours=1)
BROKEN = (
    b"<!-- thinkhow:format 1 -->\n# x\n<!-- thinkhow:session 1 -->\n"
    b"<!-- thinkhow:turn 1 user not-a-time -->\nhi\n<!-- thinkhow:closed 1 2026-10-22T10:00:00Z -->\n"
)


@pytest.fixture
def logs(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> LogCapture:
    return install_log_capture(monkeypatch, capsys)


def test_run_seed_seeds_knowledge_logs_seed_done_and_returns_0(tmp_path: Path, logs: LogCapture) -> None:
    environ = local_environ(tmp_path)
    assert run(["seed"], environ, CARDS, lambda: NOW) == 0
    assert (tmp_path / "system" / "knowledge" / "changes" / "000001.json").is_file()
    assert run(["seed"], environ, CARDS, lambda: NOW) == 0
    done = logs.events("seed_done")
    assert [line["created"] for line in done] == [True, False]


def test_run_analyze_in_local_mode_writes_the_scripted_observation_and_returns_0(
    tmp_path: Path, logs: LogCapture
) -> None:
    storage = LocalStorage(tmp_path)
    write_topic(  # turns 1-2 analyzed; turns 3-4 after more than 24 h of silence
        storage,
        ALICE,
        "t-a00000000001",
        [
            S(1, [T(1, "user", "Перша.", NOW - 40 * H), T(2, "model", "Так?", NOW - 40 * H + S1)]),
            S(2, [T(3, "user", "Друга.", NOW - 3 * H), T(4, "model", "Так?", NOW - 3 * H + S1)]),
        ],
    )
    storage.write(
        "system",
        range_path(ALICE, "t-a00000000001", 1, 2),
        observation_bytes(ALICE, "t-a00000000001", 1, 2, NOW - 30 * H),
        "application/json",
    )
    write_topic(  # a topic with nothing new
        storage, BOB, "t-b00000000001", [S(1, [T(1, "user", "Третя.", NOW - 9 * H)])]
    )
    storage.write(
        "system",
        range_path(BOB, "t-b00000000001", 1, 1),
        observation_bytes(BOB, "t-b00000000001", 1, 1, NOW - 8 * H),
        "application/json",
    )
    assert run(["analyze"], local_environ(tmp_path), CARDS, lambda: NOW) == 0
    raw = storage.read("system", range_path(ALICE, "t-a00000000001", 3, 4))
    assert raw is not None
    assert ObservationSet.model_validate_json(raw) == ObservationSet(
        uid=ALICE,
        topic_id="t-a00000000001",
        first_turn=3,
        last_turn=4,
        analyzed_at=NOW,
        observations=[
            Observation(
                id=f"{ALICE}/t-a00000000001/t3-t4/1",
                turn=3,  # the first value of the schema's enum
                link=f"/topics/{ALICE}/t-a00000000001#t3",
                kind="progress",
                worked=True,
                finding="(локальний режим) Людина назвала план; фасилітатор поставив одне питання.",
                cause="facilitation",
                card_id=None,  # no routing.json
                analyzed_at=NOW,
            )
        ],
    )
    done = logs.events("analyze_done")
    assert len(done) == 1
    assert (done[0]["written"], done[0]["skipped"], done[0]["failed"]) == (1, 1, 0)


def test_run_unknown_command_prints_usage_to_stderr_and_returns_2(tmp_path: Path, logs: LogCapture) -> None:
    assert run(["frobnicate"], local_environ(tmp_path), CARDS, lambda: NOW) == 2
    assert logs.err().strip() != ""


def test_run_raises_config_error_on_bad_settings(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        run(["analyze"], {}, CARDS, lambda: NOW)  # cloud mode without buckets and owner
    with pytest.raises(ConfigError):
        run(["seed"], {**local_environ(tmp_path), "CLOUD_RUN_JOB": "analyze"}, CARDS, lambda: NOW)


def test_seam2_run_with_a_broken_conversation_logs_the_topic_analyzes_the_rest_and_returns_0(
    tmp_path: Path, logs: LogCapture
) -> None:
    storage = LocalStorage(tmp_path)
    write_topic(
        storage,
        ALICE,
        "t-a00000000001",
        [S(1, [T(1, "user", "План.", NOW - 3 * H), T(2, "model", "Так?", NOW - 3 * H + S1)])],
    )
    storage.write("users", f"{BOB}/t-b00000000001/conversation.md", BROKEN, "text/markdown; charset=utf-8")
    with pytest.raises(ValueError):  # the premise: the file does not parse
        topic_sessions(storage, TopicRef(BOB, "t-b00000000001"), NOW)
    write_topic(storage, BOB, "t-b00000000002", [S(1, [T(1, "user", "Інший план.", NOW - 3 * H)])])

    assert run(["analyze"], local_environ(tmp_path), CARDS, lambda: NOW) == 0

    assert storage.read("system", range_path(ALICE, "t-a00000000001", 1, 2)) is not None
    assert storage.read("system", range_path(BOB, "t-b00000000002", 1, 1)) is not None
    failed = logs.events("analyze_failed")
    assert len(failed) == 1
    assert failed[0]["uid"] == BOB and failed[0]["topic_id"] == "t-b00000000001"
    assert failed[0].get("session_no") is None
    done = logs.events("analyze_done")
    assert len(done) == 1
    assert (done[0]["written"], done[0]["skipped"], done[0]["failed"]) == (2, 0, 1)
