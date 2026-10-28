"""Contract tests of skel-learning: analyze (slice tester; from the contract, not the code).

Corrected by objection (round 2, slice continuous-analysis, task 202): analysis no longer waits for a closed
session — every topic with turns after the last analyzed one gets one call, the file is
`t<first>-t<last>.json`, `Observation` carries `first_turn`/`last_turn`, `analyze_failed` carries
`first_turn`/`last_turn` and no `session_no`. A session boundary is set up by 24 h of silence (the injected
`now`) or by a hand-written legacy `closed` marker — never by the button, which is gone.

Carried over by objection (task 720, answer A) to analysis-rules: the model answers
`{"observations": [...]}` with `kind`; the file is an `ObservationSet` whose observations carry `id`,
`turn`, `link`, `kind`, `card_id` (None without `routing.json`) and the set's `analyzed_at`. The context of
a new session is every analyzed turn of the topic (one-conversation, Q2). Every other check — calls,
report, cursor, failure, log — is unchanged.
"""

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
    observation_bytes,
    range_path,
    validation_error,
    write_topic,
)

from thinkhow.learning.analyze import ANALYZER, AnalyzeReport, analyze
from thinkhow.learning.observations import Observation, ObservationSet
from thinkhow.platform.llm import LlmUnavailable, Turn
from thinkhow.platform.storage import LocalStorage

H = timedelta(hours=1)
A1, A2 = "t-a00000000001", "t-a00000000002"
B1, B2, B3 = "t-b00000000001", "t-b00000000002", "t-b00000000003"
CONTEXT = "[Контекст — уже проаналізовано, не якір:]"
NEW = "[Нові репліки:]"


@pytest.fixture
def logs(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> LogCapture:
    return install_log_capture(monkeypatch, capsys)


def seam1_world(storage: LocalStorage) -> bytes:
    """Topics of two people: open (a reply minutes ago), closed by silence, closed by a legacy marker,
    already observed (`t1-t2.json`), an empty session (legacy marker, no turns)."""
    write_topic(  # an open conversation: no marker, no silence
        storage,
        ALICE,
        A1,
        [
            S(
                1,
                [
                    T(1, "user", "відкрита-маркер план", NOW - 10 * S1),
                    T(2, "model", "Питання?", NOW - 5 * S1),
                ],
            )
        ],
    )
    write_topic(  # last turn at T, now = T + 24h: closed by silence
        storage,
        ALICE,
        A2,
        [S(1, [T(1, "user", "тиша-маркер план", NOW - H24 - 60 * S1), T(2, "model", "Питання?", NOW - H24)])],
    )
    write_topic(  # a legacy closed marker written by an earlier version
        storage,
        BOB,
        B1,
        [
            S(
                1,
                [
                    T(1, "user", "старий-маркер план", NOW - 3 * H),
                    T(2, "model", "Питання?", NOW - 3 * H + S1),
                ],
                closed=NOW - 2 * H,
            )
        ],
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
            )
        ],
    )
    present = observation_bytes(BOB, B2, 1, 2, NOW - 20 * H)
    storage.write("system", range_path(BOB, B2, 1, 2), present, "application/json")
    write_topic(storage, BOB, B3, [S(1, [], closed=NOW - 5 * H)])  # an empty session with a legacy marker
    return present


def test_seam1_one_call_per_topic_with_new_turns_none_for_the_rest(tmp_path: Path) -> None:
    storage = SpyStorage(tmp_path)
    present = seam1_world(storage)
    llm = FakeLlm()
    report = analyze(storage, llm, NOW)
    assert len(llm.calls_with("відкрита-маркер")) == 1
    assert len(llm.calls_with("тиша-маркер")) == 1
    assert len(llm.calls_with("старий-маркер")) == 1
    assert llm.calls_with("наявне-маркер") == []
    assert len(llm.calls) == 3  # nothing for the empty session either
    assert report == AnalyzeReport(written=3, skipped=2, failed=0)
    for uid, topic_id in ((ALICE, A1), (ALICE, A2), (BOB, B1)):
        assert storage.read("system", range_path(uid, topic_id, 1, 2)) is not None, topic_id
    assert storage.read("system", range_path(BOB, B2, 1, 2)) == present
    assert [p for p in (tmp_path / "system").rglob("*") if p.is_file() and B3 in p.parts] == []


def test_observation_carries_the_range_the_answer_and_now(tmp_path: Path) -> None:
    storage = SpyStorage(tmp_path)
    seam1_world(storage)
    analyze(storage, FakeLlm(), NOW)
    by_path = {w.path: w for w in storage.writes if w.bucket == "system"}
    for uid, topic_id in ((ALICE, A1), (ALICE, A2), (BOB, B1)):
        rec = by_path[range_path(uid, topic_id, 1, 2)]
        assert rec.op == "write"
        assert rec.content_type == "application/json"
        got = ObservationSet.model_validate_json(rec.data)
        assert got == ObservationSet(
            uid=uid,
            topic_id=topic_id,
            first_turn=1,
            last_turn=2,
            analyzed_at=NOW,
            observations=[
                Observation(
                    id=f"{uid}/{topic_id}/t1-t2/1",
                    turn=2,  # FakeLlm answers the last anchor of the enum
                    link=f"/topics/{uid}/{topic_id}#t2",
                    kind="stuck",
                    worked=False,
                    finding="Фасилітатор поставив одне питання.",
                    cause="method",
                    card_id=None,  # no routing.json
                    analyzed_at=NOW,
                )
            ],
        )


def lines_of(llm: FakeLlm) -> list[str]:
    assert len(llm.calls) == 1
    call = llm.calls[0]
    assert call.system == ANALYZER
    assert call.rev is None
    assert len(call.contents) == 1 and isinstance(call.contents[0], Turn)
    assert call.contents[0].role == "user"
    return [line for line in call.contents[0].text.split("\n") if line.strip()]


def test_one_generate_json_call_with_analyzer_one_user_turn_of_numbered_lines_earlier_session_as_context(
    tmp_path: Path,
) -> None:
    """The first new turn opens a session (after 24 h of silence): the analyzed turns of the earlier
    session come as context, then the new ones (one-conversation, Q2: «Контекст аналізатора — усі вже
    проаналізовані репліки теми перед першою новою»; was: only the new turns, no headers)."""
    storage = LocalStorage(tmp_path)
    write_topic(
        storage,
        ALICE,
        A1,
        [
            S(1, [T(1, "user", "перша-сесія", NOW - 40 * H), T(2, "model", "Так?", NOW - 40 * H + S1)]),
            S(
                2,
                [
                    T(3, "user", "Хочу відкрити кав'ярню за три місяці.", NOW - 3 * H),
                    T(4, "model", "Що може піти не так?", NOW - 3 * H + 9 * S1),
                ],
            ),
        ],
    )
    storage.write(
        "system",
        range_path(ALICE, A1, 1, 2),
        observation_bytes(ALICE, A1, 1, 2, NOW - 30 * H),
        "application/json",
    )
    llm = FakeLlm()
    analyze(storage, llm, NOW)
    assert lines_of(llm) == [
        CONTEXT,
        "#1 людина: перша-сесія",
        "#2 фасилітатор: Так?",
        NEW,
        "#3 людина: Хочу відкрити кав'ярню за три місяці.",
        "#4 фасилітатор: Що може піти не так?",
    ]


def test_new_turns_in_the_same_session_come_after_the_context_of_the_analyzed_ones(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    write_topic(
        storage,
        ALICE,
        A1,
        [
            S(
                1,
                [
                    T(1, "user", "Хочу змінити роботу.", NOW - 5 * H),
                    T(2, "model", "Що саме не так зараз?", NOW - 5 * H + S1),
                    T(3, "user", "Немає росту.", NOW - H),
                    T(4, "model", "Як виглядав би ріст?", NOW - H + S1),
                ],
            )
        ],
    )
    storage.write(
        "system",
        range_path(ALICE, A1, 1, 2),
        observation_bytes(ALICE, A1, 1, 2, NOW - 4 * H),
        "application/json",
    )
    llm = FakeLlm()
    analyze(storage, llm, NOW)
    assert lines_of(llm) == [
        CONTEXT,
        "#1 людина: Хочу змінити роботу.",
        "#2 фасилітатор: Що саме не так зараз?",
        NEW,
        "#3 людина: Немає росту.",
        "#4 фасилітатор: Як виглядав би ріст?",
    ]


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
    seam1_world(storage)  # 3 to write, 1 observed, 1 empty
    llm = FakeLlm(fail={"тиша-маркер": LlmUnavailable("down")})
    report = analyze(storage, llm, NOW)
    assert report == AnalyzeReport(written=2, skipped=2, failed=1)
    done = logs.events("analyze_done")
    assert len(done) == 1
    assert (done[0]["written"], done[0]["skipped"], done[0]["failed"]) == (2, 2, 1)
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
                )
            ],
        )
    llm = FakeLlm(fail={"зламана-відповідь": validation_error, "недоступна-модель": LlmUnavailable("down")})
    report = analyze(storage, llm, NOW)
    assert report == AnalyzeReport(written=1, skipped=0, failed=2)
    assert not (tmp_path / "system" / "learning" / "observations" / ALICE).exists()
    assert storage.read("system", range_path(BOB, B1, 1, 2)) is not None
    failed = logs.events("analyze_failed")
    assert len(failed) == 2
    by_topic = {line["topic_id"]: line for line in failed}
    assert set(by_topic) == {A1, A2}
    for topic_id, cls in ((A1, "ValidationError"), (A2, "LlmUnavailable")):
        line = by_topic[topic_id]
        assert line["uid"] == ALICE
        assert (line["first_turn"], line["last_turn"]) == (1, 2)
        assert "session_no" not in line, line
        assert cls in [v for v in line.values() if isinstance(v, str)], line
    dumped = logs.raw()
    for text in (*texts.values(), "Особлива-відповідь?"):
        assert text not in dumped


def test_a_failed_topic_is_tried_again_on_the_next_run(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    write_topic(
        storage,
        ALICE,
        A1,
        [S(1, [T(1, "user", "повтор-маркер", NOW - 3 * H), T(2, "model", "Так?", NOW - 3 * H + S1)])],
    )
    first = analyze(storage, FakeLlm(fail={"повтор-маркер": LlmUnavailable("down")}), NOW)
    assert first == AnalyzeReport(written=0, skipped=0, failed=1)
    assert not (tmp_path / "system" / "learning" / "observations" / ALICE).exists()
    llm = FakeLlm()
    second = analyze(storage, llm, NOW + H)
    assert len(llm.calls) == 1
    assert second == AnalyzeReport(written=1, skipped=0, failed=0)
    assert storage.read("system", range_path(ALICE, A1, 1, 2)) is not None
