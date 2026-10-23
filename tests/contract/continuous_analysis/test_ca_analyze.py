"""Contract tests of continuous-analysis: the analyzer (slice tester; from the contract, not the code)."""

from pathlib import Path

import pytest
from ca_fakes import (
    ALICE,
    BOB,
    CTX,
    DAY,
    LS,
    NEW,
    NOW,
    FakeLlm,
    H,
    LogCapture,
    M,
    answer_now,
    install_log_capture,
    legacy_topic,
    new_topic,
    obs,
    obs_names,
    pair,
    put_obs,
    say,
    say_unanswered,
    validation_error,
)

from thinkhow.learning.analyze import ANALYZER, AnalyzeReport, analyze
from thinkhow.platform.llm import LlmUnavailable, Turn
from thinkhow.platform.storage import LocalStorage


@pytest.fixture
def logs(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> LogCapture:
    return install_log_capture(monkeypatch, capsys)


# --- hardest seams ---------------------------------------------------------------------------------


def test_seam1_the_cursor_comes_from_file_names_across_runs(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    t0 = NOW - 10 * H
    ref = new_topic(storage, ALICE, t0 - M)
    say(storage, ALICE, ref, "Хочу відкрити кав'ярню.", "Що може піти не так?", t0)

    llm1 = FakeLlm()
    assert analyze(storage, llm1, NOW) == AnalyzeReport(written=1, skipped=0, failed=0)
    assert len(llm1.calls) == 1
    assert obs_names(storage, ref) == {"t1-t2.json"}

    llm2 = FakeLlm()
    assert analyze(storage, llm2, NOW + M) == AnalyzeReport(written=0, skipped=1, failed=0)
    assert llm2.calls == []
    assert obs_names(storage, ref) == {"t1-t2.json"}

    say(storage, ALICE, ref, "Гроші скінчаться.", "Коли саме?", NOW + H)  # same session
    llm3 = FakeLlm()
    assert analyze(storage, llm3, NOW + 2 * H) == AnalyzeReport(written=1, skipped=0, failed=0)
    assert len(llm3.calls) == 1
    assert llm3.calls[0].lines() == [
        CTX,
        "#1 людина: Хочу відкрити кав'ярню.",
        "#2 фасилітатор: Що може піти не так?",
        NEW,
        "#3 людина: Гроші скінчаться.",
        "#4 фасилітатор: Коли саме?",
    ]
    assert llm3.calls[0].anchors() == ["t3", "t4"]
    assert obs_names(storage, ref) == {"t1-t2.json", "t3-t4.json"}
    assert obs(storage, ref, "t3-t4.json")["turn"] in (3, 4)


def test_seam1_turns_after_24h_of_silence_open_a_session_and_go_without_context(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    t0 = NOW - 3 * DAY
    ref = new_topic(storage, ALICE, t0 - M)
    say(storage, ALICE, ref, "Перша думка.", "Перше питання?", t0)
    analyze(storage, FakeLlm(), t0 + H)
    say(storage, ALICE, ref, "Друга думка.", "Друге питання?", t0 + 2 * H)
    analyze(storage, FakeLlm(), t0 + 3 * H)
    say(storage, ALICE, ref, "Повернувся через добу.", "Що змінилось?", t0 + 2 * H + DAY)
    llm = FakeLlm()
    analyze(storage, llm, t0 + 3 * H + DAY)
    assert len(llm.calls) == 1
    assert llm.calls[0].lines() == ["#5 людина: Повернувся через добу.", "#6 фасилітатор: Що змінилось?"]
    assert llm.calls[0].anchors() == ["t5", "t6"]
    assert obs_names(storage, ref) == {"t1-t2.json", "t3-t4.json", "t5-t6.json"}


def test_seam2_legacy_s_files_move_the_cursor_and_stay_untouched(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    old = NOW - 10 * DAY
    # session 1 closed by the legacy button, session 2 open; s1.json already there
    a = legacy_topic(
        storage,
        ALICE,
        [LS(1, pair(1, "а-перша", old), closed=old + H), LS(2, pair(3, "а-друга", NOW - 2 * H))],
    )
    a_s1 = put_obs(storage, a, "s1.json")
    # s<n> with no such session, and s<n> of an empty session: the cursor does not move
    c = legacy_topic(storage, ALICE, [LS(1, pair(1, "в-немає", NOW - 3 * H))])
    put_obs(storage, c, "s7.json")
    d = legacy_topic(storage, ALICE, [LS(1, [], closed=old), LS(2, pair(1, "г-порожня", NOW - 3 * H))])
    put_obs(storage, d, "s1.json")
    # two old sessions, only s2.json: the maximum counts
    b = legacy_topic(
        storage,
        BOB,
        [
            LS(1, pair(1, "б-перша", old)),
            LS(2, pair(3, "б-друга", old + 2 * DAY)),
            LS(3, pair(5, "б-третя", NOW - 3 * H)),
        ],
    )
    put_obs(storage, b, "s2.json")

    llm = FakeLlm()
    analyze(storage, llm, NOW)

    calls = llm.calls_with("а-")
    assert len(calls) == 1
    call_a = calls[0]
    assert call_a.lines() == ["#3 людина: а-друга людина 3", "#4 фасилітатор: а-друга фасилітатор 4"]
    assert obs_names(storage, a) == {"s1.json", "t3-t4.json"}
    assert storage.read("system", f"learning/observations/{a.uid}/{a.topic_id}/s1.json") == a_s1

    calls = llm.calls_with("в-немає")
    assert len(calls) == 1
    call_c = calls[0]
    assert call_c.anchors() == ["t1", "t2"]
    assert obs_names(storage, c) == {"s7.json", "t1-t2.json"}

    calls = llm.calls_with("г-порожня")
    assert len(calls) == 1
    call_d = calls[0]
    assert call_d.anchors() == ["t1", "t2"]
    assert obs_names(storage, d) == {"s1.json", "t1-t2.json"}

    calls = llm.calls_with("б-")
    assert len(calls) == 1
    call_b = calls[0]
    assert call_b.lines() == ["#5 людина: б-третя людина 5", "#6 фасилітатор: б-третя фасилітатор 6"]
    assert llm.calls_with("б-перша") == []
    assert obs_names(storage, b) == {"s2.json", "t5-t6.json"}
    assert len(llm.calls) == 4


def test_seam3_a_failure_writes_nothing_and_the_turns_come_again(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    ref = new_topic(storage, ALICE, NOW - 4 * H)
    say(storage, ALICE, ref, "Хочу змінити роботу.", "Чому зараз?", NOW - 3 * H)
    first = analyze(storage, FakeLlm(fail_all=LlmUnavailable("down")), NOW - 2 * H)
    assert first == AnalyzeReport(written=0, skipped=0, failed=1)
    assert obs_names(storage, ref) == set()

    say_unanswered(storage, ALICE, ref, "Бо набридло.", NOW - H)
    llm = FakeLlm()
    analyze(storage, llm, NOW)
    assert len(llm.calls) == 1
    assert llm.calls[0].lines() == [
        "#1 людина: Хочу змінити роботу.",
        "#2 фасилітатор: Чому зараз?",
        "#3 людина: Бо набридло.",
    ]
    assert obs_names(storage, ref) == {"t1-t3.json"}


def test_seam5_an_open_conversation_is_analyzed_at_once(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    ref = new_topic(storage, ALICE, NOW - 10 * M)
    say(storage, ALICE, ref, "Хочу переїхати.", "Куди?", NOW - 5 * M)
    llm = FakeLlm()
    assert analyze(storage, llm, NOW) == AnalyzeReport(written=1, skipped=0, failed=0)
    assert len(llm.calls) == 1
    assert obs_names(storage, ref) == {"t1-t2.json"}


# --- the flow --------------------------------------------------------------------------------------


def test_one_generate_json_call_with_analyzer_one_user_turn_and_no_rev(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    ref = new_topic(storage, ALICE, NOW - 2 * H)
    say(storage, ALICE, ref, "Хочу відкрити кав'ярню.", "Що може піти не так?", NOW - H)
    llm = FakeLlm()
    analyze(storage, llm, NOW)
    assert len(llm.calls) == 1
    call = llm.calls[0]
    assert call.system == ANALYZER
    assert call.rev is None
    assert len(call.contents) == 1 and isinstance(call.contents[0], Turn)
    assert call.contents[0].role == "user"


def test_new_turns_of_two_sessions_go_in_one_call_with_context_of_the_first_ones_session(
    tmp_path: Path,
) -> None:
    storage = LocalStorage(tmp_path)
    t0 = NOW - 3 * DAY
    ref = new_topic(storage, ALICE, t0 - M)
    say(storage, ALICE, ref, "Один.", "Два?", t0)
    analyze(storage, FakeLlm(), t0 + H)
    say(storage, ALICE, ref, "Три.", "Чотири?", t0 + 2 * H)  # same session
    say(storage, ALICE, ref, "П'ять.", "Шість?", t0 + 2 * H + DAY)  # a new session
    llm = FakeLlm()
    assert analyze(storage, llm, t0 + 3 * H + DAY) == AnalyzeReport(written=1, skipped=0, failed=0)
    assert len(llm.calls) == 1
    assert llm.calls[0].lines() == [
        CTX,
        "#1 людина: Один.",
        "#2 фасилітатор: Два?",
        NEW,
        "#3 людина: Три.",
        "#4 фасилітатор: Чотири?",
        "#5 людина: П'ять.",
        "#6 фасилітатор: Шість?",
    ]
    assert llm.calls[0].anchors() == ["t3", "t4", "t5", "t6"]
    assert obs_names(storage, ref) == {"t1-t2.json", "t3-t6.json"}


def test_an_unanswered_last_turn_of_the_person_is_analyzed_and_its_answer_goes_next_run(
    tmp_path: Path,
) -> None:
    storage = LocalStorage(tmp_path)
    ref = new_topic(storage, ALICE, NOW - 2 * H)
    say_unanswered(storage, ALICE, ref, "Хочу почати бігати.", NOW - H)
    llm1 = FakeLlm()
    assert analyze(storage, llm1, NOW) == AnalyzeReport(written=1, skipped=0, failed=0)
    assert llm1.calls[0].lines() == ["#1 людина: Хочу почати бігати."]
    assert llm1.calls[0].anchors() == ["t1"]
    assert obs_names(storage, ref) == {"t1-t1.json"}

    answer_now(storage, ALICE, ref, "Що заважало досі?", NOW + 10 * M)
    llm2 = FakeLlm()
    analyze(storage, llm2, NOW + H)
    assert llm2.calls[0].lines() == [
        CTX,
        "#1 людина: Хочу почати бігати.",
        NEW,
        "#2 фасилітатор: Що заважало досі?",
    ]
    assert llm2.calls[0].anchors() == ["t2"]
    assert obs_names(storage, ref) == {"t1-t1.json", "t2-t2.json"}


def test_observation_file_has_the_range_the_anchor_and_link_and_no_session_fields(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    ref = new_topic(storage, ALICE, NOW - 5 * H)
    say(storage, ALICE, ref, "Один.", "Два?", NOW - 4 * H)
    analyze(storage, FakeLlm(), NOW - 3 * H)
    say(storage, ALICE, ref, "Три.", "Чотири?", NOW - 2 * H)
    analyze(storage, FakeLlm(pick="first"), NOW)
    got = obs(storage, ref, "t3-t4.json")
    assert got["uid"] == ALICE.id
    assert got["topic_id"] == ref.topic_id
    assert got["first_turn"] == 3
    assert got["last_turn"] == 4
    assert got["turn"] == 3
    assert got["link"] == f"/topics/{ALICE.id}/{ref.topic_id}#t3"
    assert got["worked"] is False
    assert got["finding"] == "Фасилітатор поставив одне питання."
    assert got["cause"] == "method"
    assert "analyzed_at" in got
    assert "session_no" not in got
    assert "closed_at" not in got


def test_report_counts_written_skipped_failed_per_topic(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    good = new_topic(storage, ALICE, NOW - 3 * H)
    say(storage, ALICE, good, "добра-тема", "Так?", NOW - 2 * H)
    empty = new_topic(storage, ALICE, NOW - 3 * H)
    bad = new_topic(storage, BOB, NOW - 3 * H)
    say(storage, BOB, bad, "зламана-тема", "Так?", NOW - 2 * H)
    llm = FakeLlm(fail={"зламана-тема": LlmUnavailable("down")})
    assert analyze(storage, llm, NOW) == AnalyzeReport(written=1, skipped=1, failed=1)
    assert llm.calls_with("добра-тема") and llm.calls_with("зламана-тема")
    assert len(llm.calls) == 2
    assert obs_names(storage, good) == {"t1-t2.json"}
    assert obs_names(storage, empty) == set()
    assert obs_names(storage, bad) == set()


def test_analyze_failed_line_has_first_and_last_turn_and_no_session_no(
    tmp_path: Path, logs: LogCapture
) -> None:
    storage = LocalStorage(tmp_path)
    a = new_topic(storage, ALICE, NOW - 5 * H)
    say(storage, ALICE, a, "зламана-відповідь один", "Два?", NOW - 4 * H)
    analyze(storage, FakeLlm(), NOW - 3 * H)
    say(storage, ALICE, a, "зламана-відповідь три", "Чотири?", NOW - 2 * H)
    b = new_topic(storage, BOB, NOW - 5 * H)
    say(storage, BOB, b, "недоступна-модель", "Так?", NOW - 4 * H)
    llm = FakeLlm(fail={"зламана-відповідь": validation_error, "недоступна-модель": LlmUnavailable("down")})
    assert analyze(storage, llm, NOW) == AnalyzeReport(written=0, skipped=0, failed=2)
    failed = logs.events("analyze_failed")
    by_topic = {line["topic_id"]: line for line in failed}
    assert set(by_topic) == {a.topic_id, b.topic_id}
    assert (by_topic[a.topic_id]["first_turn"], by_topic[a.topic_id]["last_turn"]) == (3, 4)
    assert (by_topic[b.topic_id]["first_turn"], by_topic[b.topic_id]["last_turn"]) == (1, 2)
    for line in failed:
        assert "session_no" not in line
    assert obs_names(storage, a) == {"t1-t2.json"}
    assert obs_names(storage, b) == set()


def test_any_other_file_name_does_not_move_the_cursor(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    ref = new_topic(storage, ALICE, NOW - 3 * H)
    say(storage, ALICE, ref, "Хочу вчитись.", "Чого саме?", NOW - 2 * H)
    others = {"notes.json", "t9.json", "x1-t9.json", "s.json", "t1-t9.txt", "sx.json"}
    for name in others:
        put_obs(storage, ref, name)
    llm = FakeLlm()
    analyze(storage, llm, NOW)
    assert len(llm.calls) == 1
    assert llm.calls[0].lines() == ["#1 людина: Хочу вчитись.", "#2 фасилітатор: Чого саме?"]
    assert obs_names(storage, ref) == others | {"t1-t2.json"}


def test_analyzer_instructions_speak_of_new_turns_and_the_context(tmp_path: Path) -> None:
    text = " ".join(ANALYZER.split())
    assert (
        "Ти читаєш нові репліки однієї теми (з часу минулого аналізу), у яких фасилітатор вів людину" in text
    )
    assert "у нових репліках" in text
    assert "у цій сесії" not in text
    assert (
        "Репліки під рядком «Контекст» уже проаналізовано — вони лише для розуміння; "
        "висновок і якір — лише про нові" in text
    )
