"""Contract tests of skel-learning: analyze (slice tester; from the contract, not the code)."""

import re
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from skell_fakes import (
    ALICE,
    BOB,
    H24,
    NOW,
    S1,
    FakeLlm,
    LogCapture,
    S,
    SpyStorage,
    T,
    install_log_capture,
    obs_path,
    validation_error,
    write_topic,
)

from thinkhow.learning.analyze import ANALYZER, AnalyzeReport, Observation, analyze
from thinkhow.platform.llm import LlmUnavailable, Turn
from thinkhow.platform.storage import LocalStorage

H = timedelta(hours=1)
A1, A2 = "t-a00000000001", "t-a00000000002"
B1, B2, B3 = "t-b00000000001", "t-b00000000002", "t-b00000000003"


@pytest.fixture
def logs(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> LogCapture:
    return install_log_capture(monkeypatch, capsys)


def existing_observation(uid: str, topic_id: str) -> bytes:
    return (
        Observation(
            uid=uid,
            topic_id=topic_id,
            session_no=1,
            turn=1,
            link=f"/topics/{uid}/{topic_id}#t1",
            worked=True,
            finding="Вже проаналізовано раніше.",
            cause="circumstances",
            closed_at=NOW - 30 * H,
            analyzed_at=NOW - 20 * H,
        )
        .model_dump_json()
        .encode("utf-8")
    )


def seam1_world(storage: LocalStorage) -> bytes:
    """Topics of two people: closed by button, closed by silence, open, already observed, empty+button."""
    write_topic(
        storage,
        ALICE,
        A1,
        [
            S(
                1,
                [
                    T(1, "user", "кнопка-маркер план", NOW - 3 * H),
                    T(2, "model", "Питання?", NOW - 3 * H + 9 * S1),
                ],
                closed=NOW - 2 * H,
            )
        ],
    )
    write_topic(  # last turn at T, now = T + 24h: closed by silence
        storage,
        ALICE,
        A2,
        [S(1, [T(1, "user", "тиша-маркер план", NOW - H24 - 60 * S1), T(2, "model", "Питання?", NOW - H24)])],
    )
    write_topic(  # last turn at T, now = T + 24h - 1s: still open
        storage,
        BOB,
        B1,
        [S(1, [T(1, "user", "відкрита-маркер план", NOW - H24), T(2, "model", "Питання?", NOW - H24 + S1)])],
    )
    write_topic(
        storage,
        BOB,
        B2,
        [
            S(
                1,
                [
                    T(1, "user", "наявне-маркер план", NOW - 40 * H),
                    T(2, "model", "Питання?", NOW - 40 * H + S1),
                ],
                closed=NOW - 30 * H,
            )
        ],
    )
    present = existing_observation(BOB, B2)
    storage.write("system", obs_path(BOB, B2, 1), present, "application/json")
    write_topic(storage, BOB, B3, [S(1, [], closed=NOW - 5 * H)])  # empty session closed by the button
    return present


def test_seam1_one_call_per_closed_unobserved_session_none_for_the_rest(tmp_path: Path) -> None:
    storage = SpyStorage(tmp_path)
    present = seam1_world(storage)
    llm = FakeLlm()
    report = analyze(storage, llm, NOW)
    assert len(llm.calls_with("кнопка-маркер")) == 1
    assert len(llm.calls_with("тиша-маркер")) == 1
    assert llm.calls_with("відкрита-маркер") == []
    assert llm.calls_with("наявне-маркер") == []
    assert len(llm.calls) == 2  # nothing for the empty session either
    assert report == AnalyzeReport(written=2, skipped=1, failed=0)
    assert storage.read("system", obs_path(ALICE, A1, 1)) is not None
    assert storage.read("system", obs_path(ALICE, A2, 1)) is not None
    assert storage.read("system", obs_path(BOB, B1, 1)) is None
    assert storage.read("system", obs_path(BOB, B3, 1)) is None
    assert storage.read("system", obs_path(BOB, B2, 1)) == present


def test_observation_carries_the_session_the_answer_and_now(tmp_path: Path) -> None:
    storage = SpyStorage(tmp_path)
    seam1_world(storage)
    analyze(storage, FakeLlm(), NOW)
    by_path = {w.path: w for w in storage.writes if w.bucket == "system"}
    expected = {
        A1: NOW - 2 * H,  # the time of the closed marker
        A2: NOW,  # the last turn + 24h
    }
    for topic_id, closed_at in expected.items():
        rec = by_path[obs_path(ALICE, topic_id, 1)]
        assert rec.op == "write"
        assert rec.content_type == "application/json"
        got = Observation.model_validate_json(rec.data)
        assert got == Observation(
            uid=ALICE,
            topic_id=topic_id,
            session_no=1,
            turn=2,
            link=f"/topics/{ALICE}/{topic_id}#t2",
            worked=False,
            finding="Фасилітатор поставив одне питання.",
            cause="method",
            closed_at=closed_at,
            analyzed_at=NOW,
        )


def test_one_generate_json_call_with_analyzer_one_user_turn_of_numbered_lines_and_the_closed_line(
    tmp_path: Path,
) -> None:
    storage = LocalStorage(tmp_path)
    write_topic(
        storage,
        ALICE,
        A1,
        [
            S(
                1,
                [T(1, "user", "перша-сесія", NOW - 9 * H), T(2, "model", "Так?", NOW - 9 * H + S1)],
                closed=NOW - 8 * H,
            ),
            S(
                2,
                [
                    T(3, "user", "Хочу відкрити кав'ярню за три місяці.", NOW - 3 * H),
                    T(4, "model", "Що може піти не так?", NOW - 3 * H + 9 * S1),
                ],
                closed=NOW - 2 * H,
            ),
        ],
    )
    observation = existing_observation(ALICE, A1)
    storage.write("system", obs_path(ALICE, A1, 1), observation, "application/json")
    llm = FakeLlm()
    analyze(storage, llm, NOW)
    assert len(llm.calls) == 1
    call = llm.calls[0]
    assert call.system == ANALYZER
    assert call.rev is None
    assert len(call.contents) == 1 and isinstance(call.contents[0], Turn)
    assert call.contents[0].role == "user"
    lines = [line for line in call.contents[0].text.split("\n") if line.strip()]
    assert lines[:2] == [
        "#3 людина: Хочу відкрити кав'ярню за три місяці.",
        "#4 фасилітатор: Що може піти не так?",
    ]
    assert len(lines) == 3
    marker = re.fullmatch(r"\[Сесія 2 закрита (\S+)\]", lines[2])
    assert marker, lines[2]
    assert datetime.fromisoformat(marker.group(1)) == NOW - 2 * H


def test_now_without_time_zone_is_value_error_at_once(tmp_path: Path) -> None:
    naive = datetime(2026, 10, 22, 18, 0, 0)
    llm = FakeLlm()
    with pytest.raises(ValueError):
        analyze(LocalStorage(tmp_path / "empty"), llm, naive)  # no topic at all
    storage = SpyStorage(tmp_path / "full")
    seam1_world(storage)
    writes_before = len(storage.writes)
    with pytest.raises(ValueError):
        analyze(storage, llm, naive)
    assert llm.calls == []
    assert len(storage.writes) == writes_before


def test_analyze_done_line_at_the_end_carries_the_report(tmp_path: Path, logs: LogCapture) -> None:
    storage = LocalStorage(tmp_path)
    seam1_world(storage)  # 2 to write, 1 present
    llm = FakeLlm(fail={"тиша-маркер": LlmUnavailable("down")})
    report = analyze(storage, llm, NOW)
    assert report == AnalyzeReport(written=1, skipped=1, failed=1)
    done = logs.events("analyze_done")
    assert len(done) == 1
    assert (done[0]["written"], done[0]["skipped"], done[0]["failed"]) == (1, 1, 1)
    names = [line.get("event") for line in logs.lines()]
    assert names[-1] == "analyze_done"


def test_seam2_validation_error_and_llm_unavailable_are_logged_and_the_rest_is_written(
    tmp_path: Path, logs: LogCapture
) -> None:
    storage = LocalStorage(tmp_path)
    texts = {
        A1: "зламана-відповідь Хочу відкрити кав'ярню.",
        A2: "недоступна-модель Хочу змінити роботу.",
        B1: "добра-сесія Хочу переїхати.",
    }
    for uid, topic_id in ((ALICE, A1), (ALICE, A2), (BOB, B1)):
        write_topic(
            storage,
            uid,
            topic_id,
            [
                S(
                    1,
                    [
                        T(1, "user", texts[topic_id], NOW - 3 * H),
                        T(2, "model", "Особлива-відповідь?", NOW - 2 * H),
                    ],
                    closed=NOW - H,
                )
            ],
        )
    llm = FakeLlm(fail={"зламана-відповідь": validation_error, "недоступна-модель": LlmUnavailable("down")})
    report = analyze(storage, llm, NOW)
    assert report == AnalyzeReport(written=1, skipped=0, failed=2)
    assert storage.read("system", obs_path(ALICE, A1, 1)) is None
    assert storage.read("system", obs_path(ALICE, A2, 1)) is None
    assert storage.read("system", obs_path(BOB, B1, 1)) is not None
    failed = logs.events("analyze_failed")
    assert len(failed) == 2
    by_topic = {line["topic_id"]: line for line in failed}
    assert set(by_topic) == {A1, A2}
    for topic_id, cls in ((A1, "ValidationError"), (A2, "LlmUnavailable")):
        line = by_topic[topic_id]
        assert line["uid"] == ALICE
        assert line["session_no"] == 1
        assert cls in [v for v in line.values() if isinstance(v, str)], line
    dumped = logs.raw()
    for text in (*texts.values(), "Особлива-відповідь?"):
        assert text not in dumped


def test_a_failed_session_is_tried_again_on_the_next_run(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    write_topic(
        storage,
        ALICE,
        A1,
        [
            S(
                1,
                [T(1, "user", "повтор-маркер", NOW - 3 * H), T(2, "model", "Так?", NOW - 3 * H + S1)],
                closed=NOW - 2 * H,
            )
        ],
    )
    first = analyze(storage, FakeLlm(fail={"повтор-маркер": LlmUnavailable("down")}), NOW)
    assert first == AnalyzeReport(written=0, skipped=0, failed=1)
    assert storage.read("system", obs_path(ALICE, A1, 1)) is None
    llm = FakeLlm()
    second = analyze(storage, llm, NOW + H)
    assert len(llm.calls) == 1
    assert second == AnalyzeReport(written=1, skipped=0, failed=0)
    assert storage.read("system", obs_path(ALICE, A1, 1)) is not None
