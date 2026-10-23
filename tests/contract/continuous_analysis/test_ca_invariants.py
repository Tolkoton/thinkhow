"""Contract tests of continuous-analysis: the invariants I1-I5 (slice tester; from the contract)."""

from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

from ca_fakes import (
    ALICE,
    BOB,
    DAY,
    H_ALICE,
    LS,
    NOW,
    FakeLlm,
    H,
    M,
    SpyStorage,
    answer_now,
    conv_path,
    legacy_topic,
    make_client,
    new_topic,
    obs,
    obs_names,
    pair,
    put_obs,
    ranges,
    say,
    say_unanswered,
    stamp,
    validation_error,
)

from thinkhow.learning.analyze import AnalyzeReport, analyze
from thinkhow.platform.llm import LlmUnavailable
from thinkhow.platform.storage import LocalStorage
from thinkhow.workspace import TopicRef, open_topic


def test_I1_every_turn_is_analyzed_exactly_once_across_runs_appends_and_failures(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    t0 = NOW - 10 * DAY
    ref = new_topic(storage, ALICE, t0)
    idle = new_topic(storage, BOB, t0)  # never gets a turn
    analyze(storage, FakeLlm(), t0 + M)  # 0 turns
    assert obs_names(storage, ref) == set()

    say(storage, ALICE, ref, "Один.", "Два?", t0 + H)  # 1, 2
    analyze(storage, FakeLlm(fail_all=LlmUnavailable("down")), t0 + 2 * H)  # the model fails
    say(storage, ALICE, ref, "Три.", "Чотири?", t0 + 3 * H)  # 3, 4 in the same session
    analyze(storage, FakeLlm(), t0 + 4 * H)
    say_unanswered(storage, ALICE, ref, "П'ять.", t0 + 5 * H)  # 5, the person's turn alone
    analyze(storage, FakeLlm(), t0 + 6 * H)
    answer_now(storage, ALICE, ref, "Шість?", t0 + 7 * H)  # 6, the answer
    say(storage, ALICE, ref, "Сім.", "Вісім?", t0 + 7 * H + DAY)  # 7, 8 in a new session
    analyze(storage, FakeLlm(fail_all=validation_error), t0 + 8 * H + DAY)  # the answer is invalid
    analyze(storage, FakeLlm(), t0 + 9 * H + DAY)
    analyze(storage, FakeLlm(), t0 + 10 * H + DAY)  # nothing new: a repeat
    say(storage, ALICE, ref, "Дев'ять.", "Десять?", t0 + 11 * H + DAY)  # 9, 10
    say(storage, ALICE, ref, "Одинадцять.", "Дванадцять?", t0 + 12 * H + DAY)  # 11, 12
    analyze(storage, FakeLlm(), t0 + 13 * H + DAY)

    assert ranges(storage, ref) == [(1, 4), (5, 5), (6, 8), (9, 12)]
    assert obs_names(storage, ref) == {"t1-t4.json", "t5-t5.json", "t6-t8.json", "t9-t12.json"}
    assert obs_names(storage, idle) == set()


def test_I2_a_run_with_nothing_new_calls_no_model_and_writes_nothing_in_system(tmp_path: Path) -> None:
    storage = SpyStorage(tmp_path)
    old = NOW - 10 * DAY
    fresh = new_topic(storage, ALICE, NOW - 5 * H)
    say(storage, ALICE, fresh, "Один.", "Два?", NOW - 4 * H)
    retried = new_topic(storage, ALICE, NOW - 5 * H)
    say(storage, ALICE, retried, "Хочу.", "Чого?", NOW - 4 * H)
    analyze(storage, FakeLlm(fail_all=LlmUnavailable("down")), NOW - 3 * H)  # both fail first
    analyze(storage, FakeLlm(), NOW - 2 * H)  # then both are written
    say_unanswered(storage, ALICE, fresh, "Три.", NOW - 90 * M)
    analyze(storage, FakeLlm(), NOW - H)  # t3-t3
    legacy = legacy_topic(
        storage, BOB, [LS(1, pair(1, "стара", old), closed=old + H), LS(2, pair(3, "стара-2", old + 2 * DAY))]
    )
    put_obs(storage, legacy, "s2.json")
    mixed = legacy_topic(
        storage, BOB, [LS(1, pair(1, "змішана", old)), LS(2, pair(3, "змішана-2", NOW - 2 * H))]
    )
    put_obs(storage, mixed, "s1.json")
    put_obs(storage, mixed, "t3-t4.json")
    new_topic(storage, BOB, NOW - H)  # no turns at all
    assert obs_names(storage, fresh) == {"t1-t2.json", "t3-t3.json"}

    for now in (NOW, NOW + M, NOW + 3 * DAY):  # just after; and after the silence closed every session
        storage.writes.clear()
        llm = FakeLlm()
        report = analyze(storage, llm, now)
        assert llm.calls == [], now
        assert storage.system_writes() == [], now
        assert (report.written, report.failed) == (0, 0), now


def test_I3_a_legacy_closed_marker_keeps_its_session_and_its_place_after_a_new_turn(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    marked = NOW - 2 * H  # recent: only the marker closes the session
    cases: list[tuple[TopicRef, list[LS], int]] = []

    one = [LS(1, pair(1, "одна", NOW - 3 * H), closed=marked)]
    cases.append((legacy_topic(storage, ALICE, one), one, 2))
    then_open = [
        LS(1, pair(1, "перша", NOW - 5 * DAY), closed=NOW - 5 * DAY + H),
        LS(2, pair(3, "друга", NOW - H)),
    ]
    cases.append((legacy_topic(storage, ALICE, then_open), then_open, 2))
    two_marked = [
        LS(1, pair(1, "м1", NOW - 5 * DAY), closed=NOW - 5 * DAY + H),
        LS(2, pair(3, "м2", NOW - 3 * H), closed=marked),
    ]
    cases.append((legacy_topic(storage, ALICE, two_marked), two_marked, 3))
    empty_marked = [LS(1, [], closed=marked)]
    cases.append((legacy_topic(storage, ALICE, empty_marked), empty_marked, 2))

    for ref, sessions, last_session_after in cases:
        before = open_topic(storage, ALICE, ref, NOW).sessions
        for shown, want in zip(before, sessions, strict=False):
            assert shown.no == want.no
            assert [t.no for t in shown.turns] == [t.no for t in want.turns]
        for s in sessions:
            if s.closed is not None:
                assert before[s.no - 1].closed_at == s.closed, (ref, s.no)

        say(storage, ALICE, ref, "Нова думка.", "Нове питання?", NOW)
        after = open_topic(storage, ALICE, ref, NOW)
        assert after.sessions[-1].no == last_session_after, ref
        for s in sessions:
            if s.closed is not None:
                got = after.sessions[s.no - 1]
                assert got.closed_at == s.closed, (ref, s.no)
                assert [t.no for t in got.turns] == [t.no for t in s.turns], (ref, s.no)

        raw = (storage.read("users", conv_path(ref)) or b"").decode("utf-8")
        lines = [line for line in raw.split("\n") if line.strip()]
        for s in sessions:
            if s.closed is None:
                continue
            marker = f"<!-- thinkhow:closed {s.no} {stamp(s.closed)} -->"
            assert lines.count(marker) == 1, (ref, marker)
            at = lines.index(marker)
            assert lines[at + 1] == f"<!-- thinkhow:session {s.no + 1} -->", (ref, marker)
            previous = s.turns[-1].text if s.turns else f"<!-- thinkhow:session {s.no} -->"
            assert lines[at - 1] == previous, (ref, marker)


class Ids(HTMLParser):
    def __init__(self, html: str) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: set[str] = set()
        self.feed(html)
        self.close()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for k, v in attrs:
            if k == "id" and v is not None:
                self.ids.add(v)


def test_I4_the_anchor_lies_in_its_range_and_the_link_opens_that_turn_on_the_page(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path / "data")
    t0 = NOW - 3 * DAY
    ref = new_topic(storage, ALICE, t0 - M)
    calls = []
    say(storage, ALICE, ref, "Один.", "Два?", t0)
    calls.append(FakeLlm(pick="first"))
    analyze(storage, calls[-1], t0 + H)  # t1-t2
    say(storage, ALICE, ref, "Три.", "Чотири?", t0 + 2 * H)
    calls.append(FakeLlm(pick="first"))
    analyze(storage, calls[-1], t0 + 3 * H)  # t3-t4, with #1, #2 as context
    say_unanswered(storage, ALICE, ref, "П'ять.", t0 + 4 * H)
    calls.append(FakeLlm(pick="last"))
    analyze(storage, calls[-1], t0 + 5 * H)  # t5-t5
    answer_now(storage, ALICE, ref, "Шість?", t0 + 6 * H)
    say(storage, ALICE, ref, "Сім.", "Вісім?", t0 + 6 * H + DAY)  # a new session
    calls.append(FakeLlm(pick="first"))
    analyze(storage, calls[-1], t0 + 7 * H + DAY)  # t6-t8, with #5 as context
    calls.append(FakeLlm(pick="last"))
    analyze(storage, calls[-1], t0 + 8 * H + DAY)  # nothing new

    assert [len(llm.calls) for llm in calls] == [1, 1, 1, 1, 0]
    assert [llm.calls[0].anchors() for llm in calls[:4]] == [
        ["t1", "t2"],
        ["t3", "t4"],
        ["t5"],
        ["t6", "t7", "t8"],
    ]
    names = obs_names(storage, ref)
    assert names == {"t1-t2.json", "t3-t4.json", "t5-t5.json", "t6-t8.json"}
    client = make_client(tmp_path, storage, now=lambda: t0 + 9 * H + DAY)
    by_path: dict[str, set[str]] = {}
    turns = []
    for name in sorted(names):
        o = obs(storage, ref, name)
        assert o["first_turn"] <= o["turn"] <= o["last_turn"], name
        assert o["link"] == f"/topics/{ALICE.id}/{ref.topic_id}#t{o['turn']}", name
        link = urlparse(o["link"])
        if link.path not in by_path:
            r = client.get(link.path, headers=H_ALICE)
            assert r.status_code == 200
            by_path[link.path] = Ids(r.text).ids
        assert link.fragment in by_path[link.path], name
        turns.append(o["turn"])
    assert sorted(turns) == [1, 3, 5, 6]


def test_I5_legacy_s_files_set_the_starting_cursor_and_new_ranges_cover_the_rest(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    old = NOW - 20 * DAY

    topics: dict[str, TopicRef] = {}
    legacy: dict[str, dict[str, bytes]] = {}

    def make(key: str, sessions: list[LS], files: list[str]) -> None:
        topics[key] = legacy_topic(storage, ALICE, sessions)
        legacy[key] = {f: put_obs(storage, topics[key], f) for f in files}

    # s1 of a closed session, then an open session
    make("A", [LS(1, pair(1, "A-1", old), closed=old + H), LS(2, pair(3, "A-2", NOW - 3 * H))], ["s1.json"])
    # only s2 of three sessions: the maximum
    make(
        "B",
        [
            LS(1, pair(1, "B-1", old)),
            LS(2, pair(3, "B-2", old + 2 * DAY)),
            LS(3, pair(5, "B-3", NOW - 3 * H)),
        ],
        ["s2.json"],
    )
    # s5 with no such session
    make("C", [LS(1, pair(1, "C-1", NOW - 3 * H))], ["s5.json"])
    # s1 of an empty session
    make("D", [LS(1, [], closed=old), LS(2, pair(1, "D-2", NOW - 3 * H))], ["s1.json"])
    # s1 and s3 where session 3 does not exist: s1 counts, s3 does not
    make("E", [LS(1, pair(1, "E-1", old)), LS(2, pair(3, "E-2", NOW - 3 * H))], ["s1.json", "s3.json"])
    # every session has its s<n>
    make("F", [LS(1, pair(1, "F-1", old)), LS(2, pair(3, "F-2", old + 2 * DAY))], ["s1.json", "s2.json"])
    # s1 and s3, session 2 without a file: the maximum still wins (Q4)
    make(
        "G",
        [
            LS(1, pair(1, "G-1", old)),
            LS(2, pair(3, "G-2", old + 2 * DAY)),
            LS(3, pair(5, "G-3", old + 4 * DAY)),
        ],
        ["s1.json", "s3.json"],
    )
    # s1 together with a new-style range
    make(
        "I",
        [
            LS(1, pair(1, "I-1", old)),
            LS(2, pair(3, "I-2", old + 2 * DAY)),
            LS(3, pair(5, "I-3", NOW - 3 * H)),
        ],
        ["s1.json"],
    )
    put_obs(storage, topics["I"], "t3-t4.json", b'{"first_turn": 3, "last_turn": 4, "turn": 3}')

    first = analyze(storage, FakeLlm(fail={"B-3": LlmUnavailable("down")}), NOW)
    assert first == AnalyzeReport(written=5, skipped=2, failed=1)
    llm = FakeLlm()
    analyze(storage, llm, NOW + H)  # B again
    assert len(llm.calls) == 1 and "B-3" in llm.calls[0].text and "B-2" not in llm.calls[0].text
    say(storage, ALICE, topics["A"], "A-нова", "A-питання?", NOW + 2 * H)  # 5, 6 in session 2
    say(storage, ALICE, topics["C"], "C-нова", "C-питання?", NOW + 2 * H + DAY)  # 3, 4 in a new session
    analyze(storage, FakeLlm(), NOW + 3 * H + DAY)

    expected = {
        "A": [(3, 4), (5, 6)],
        "B": [(5, 6)],
        "C": [(1, 2), (3, 4)],
        "D": [(1, 2)],
        "E": [(3, 4)],
        "F": [],
        "G": [],
        "I": [(3, 4), (5, 6)],
    }
    for key, want in expected.items():
        assert ranges(storage, topics[key]) == want, key
        ref = topics[key]
        for name, body in legacy[key].items():
            assert storage.read("system", f"learning/observations/{ref.uid}/{ref.topic_id}/{name}") == body
