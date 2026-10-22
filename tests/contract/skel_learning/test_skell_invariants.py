"""Contract tests of skel-learning: the invariants I1–I3 (slice tester; from the contract, not the code).

The project has no property-based library: the inputs are chosen by hand from each «Domain».
"""

from datetime import timedelta
from pathlib import Path
from typing import Any

from skell_fakes import (
    ALICE,
    BOB,
    CARDS,
    H24,
    NOW,
    S1,
    FakeLlm,
    S,
    SpyStorage,
    T,
    enum_of,
    obs_path,
    tree,
    validation_error,
    write_topic,
)

from thinkhow.knowledge import seed
from thinkhow.learning.analyze import AnalyzeReport, Observation, analyze
from thinkhow.platform.llm import LlmUnavailable
from thinkhow.platform.storage import LocalStorage

H = timedelta(hours=1)


def first_anchor(anchors: list[str]) -> dict[str, Any]:
    return {
        "finding": "Питання прояснило план.",
        "worked": True,
        "cause": "facilitation",
        "anchor": anchors[0],
    }


def test_I1_anchor_is_a_turn_of_its_own_session_and_link_leads_to_it(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    # two sessions: session 2 has turns 3-4 (numbering through the topic, not within the session)
    write_topic(
        storage,
        ALICE,
        "t-a00000000001",
        [
            S(
                1,
                [T(1, "user", "i1-a-s1", NOW - 9 * H), T(2, "model", "Так?", NOW - 9 * H + S1)],
                closed=NOW - 8 * H,
            ),
            S(
                2,
                [T(3, "user", "i1-a-s2", NOW - 3 * H), T(4, "model", "Так?", NOW - 3 * H + S1)],
                closed=NOW - 2 * H,
            ),
        ],
    )
    # session 2 of ONE turn: the person's turn with no answer, then silence
    write_topic(
        storage,
        ALICE,
        "t-a00000000002",
        [
            S(
                1,
                [T(1, "user", "i1-b-s1", NOW - 60 * H), T(2, "model", "Так?", NOW - 60 * H + S1)],
                closed=NOW - 59 * H,
            ),
            S(2, [T(3, "user", "i1-b-s2", NOW - H24)]),
        ],
    )
    # a one-turn first session closed by the button
    write_topic(
        storage, BOB, "t-b00000000001", [S(1, [T(1, "user", "i1-c-s1", NOW - 5 * H)], closed=NOW - 4 * H)]
    )
    # a long session: twelve turns
    long_turns = [
        T(n, "user" if n % 2 else "model", f"i1-d-s1 репліка {n}", NOW - 20 * H + n * S1)
        for n in range(1, 13)
    ]
    write_topic(storage, BOB, "t-b00000000002", [S(1, long_turns, closed=NOW - 10 * H)])

    llm = FakeLlm(answer=first_anchor)
    report = analyze(storage, llm, NOW)
    assert report == AnalyzeReport(written=6, skipped=0, failed=0)

    expected = {  # token: (uid, topic_id, session_no, enum of the schema, turn)
        "i1-a-s1": (ALICE, "t-a00000000001", 1, ["t1", "t2"], 1),
        "i1-a-s2": (ALICE, "t-a00000000001", 2, ["t3", "t4"], 3),
        "i1-b-s1": (ALICE, "t-a00000000002", 1, ["t1", "t2"], 1),
        "i1-b-s2": (ALICE, "t-a00000000002", 2, ["t3"], 3),
        "i1-c-s1": (BOB, "t-b00000000001", 1, ["t1"], 1),
        "i1-d-s1": (BOB, "t-b00000000002", 1, [f"t{n}" for n in range(1, 13)], 1),
    }
    for token, (uid, topic_id, session_no, enum, turn) in expected.items():
        calls = llm.calls_with(token)
        assert len(calls) == 1, token
        assert enum_of(calls[0].schema) == enum, token
        raw = storage.read("system", obs_path(uid, topic_id, session_no))
        assert raw is not None, token
        got = Observation.model_validate_json(raw)
        assert got.turn == turn, token
        assert got.link == f"/topics/{uid}/{topic_id}#t{turn}", token

    # the last anchor too: session 2 of the first topic, answered with "t4"
    storage2 = LocalStorage(tmp_path / "again")
    write_topic(
        storage2,
        ALICE,
        "t-a00000000001",
        [
            S(
                1,
                [T(1, "user", "x", NOW - 9 * H), T(2, "model", "Так?", NOW - 9 * H + S1)],
                closed=NOW - 8 * H,
            ),
            S(
                2,
                [T(3, "user", "y", NOW - 3 * H), T(4, "model", "Так?", NOW - 3 * H + S1)],
                closed=NOW - 2 * H,
            ),
        ],
    )
    analyze(storage2, FakeLlm(), NOW)
    raw2 = storage2.read("system", obs_path(ALICE, "t-a00000000001", 2))
    assert raw2 is not None
    got2 = Observation.model_validate_json(raw2)
    assert (got2.turn, got2.link) == (4, f"/topics/{ALICE}/t-a00000000001#t4")


def test_I2_analyze_writes_nothing_outside_system_learning_observations(tmp_path: Path) -> None:
    storage = SpyStorage(tmp_path)
    seed(storage, CARDS)  # system/knowledge/ is present
    storage.write("system", "learning/other/note.json", b"{}", "application/json")
    ok = [T(1, "user", "i2-ok", NOW - 3 * H), T(2, "model", "Так?", NOW - 3 * H + S1)]
    write_topic(storage, ALICE, "t-a00000000001", [S(1, ok, closed=NOW - 2 * H)])
    write_topic(
        storage,
        ALICE,
        "t-a00000000002",
        [S(1, [T(1, "user", "i2-invalid", NOW - 3 * H)], closed=NOW - 2 * H)],
    )
    write_topic(
        storage,
        BOB,
        "t-b00000000001",
        [S(1, [T(1, "user", "i2-down", NOW - 3 * H)], closed=NOW - 2 * H)],
    )
    write_topic(  # open session
        storage, BOB, "t-b00000000002", [S(1, [T(1, "user", "i2-open", NOW - H)])]
    )
    write_topic(storage, BOB, "t-b00000000003", [S(1, [], closed=NOW - H)])  # empty, closed by button
    storage.write(  # a conversation.md that does not parse
        "users",
        f"{BOB}/t-b00000000004/conversation.md",
        b"<!-- thinkhow:format 1 -->\n# x\n<!-- thinkhow:session 1 -->\n"
        b"<!-- thinkhow:turn 1 user not-a-time -->\nhi\n<!-- thinkhow:closed 1 2026-10-22T10:00:00Z -->\n",
        "text/markdown; charset=utf-8",
    )
    storage.write("system", obs_path(ALICE, "t-a00000000003", 1), b'{"present": true}', "application/json")
    users_before = tree(tmp_path / "users")
    system_before = tree(tmp_path / "system")
    storage.writes.clear()

    fail = {"i2-invalid": validation_error, "i2-down": LlmUnavailable("down")}
    analyze(storage, FakeLlm(fail=fail), NOW)
    analyze(storage, FakeLlm(), NOW + 2 * H24)  # a second run: retries, skips, the open session closed

    assert storage.writes, "analyze wrote no observation at all"
    for rec in storage.writes:
        assert rec.bucket == "system", rec
        assert rec.path.startswith("learning/observations/"), rec
    assert tree(tmp_path / "users") == users_before
    system_after = tree(tmp_path / "system")
    outside = {p: d for p, d in system_after.items() if not p.startswith("learning/observations/")}
    assert outside == {p: d for p, d in system_before.items() if not p.startswith("learning/observations/")}


def test_I3_a_session_with_an_observation_is_never_sent_to_the_model_again(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    a1_s1 = S(
        1,
        [T(1, "user", "i3-a1-s1", NOW - 5 * H), T(2, "model", "Так?", NOW - 5 * H + S1)],
        closed=NOW - 4 * H,
    )
    write_topic(storage, ALICE, "t-a00000000001", [a1_s1])
    write_topic(
        storage,
        ALICE,
        "t-a00000000002",
        [S(1, [T(1, "user", "i3-a2-s1", NOW - 5 * H)], closed=NOW - 4 * H)],
    )
    write_topic(  # open at NOW (closes by silence at NOW + 1s)
        storage, BOB, "t-b00000000001", [S(1, [T(1, "user", "i3-b1-s1", NOW - H24 + S1)])]
    )
    write_topic(
        storage,
        BOB,
        "t-b00000000002",
        [S(1, [T(1, "user", "i3-b2-s1", NOW - 50 * H)], closed=NOW - 49 * H)],
    )
    present = Observation(
        uid=BOB,
        topic_id="t-b00000000002",
        session_no=1,
        turn=1,
        link=f"/topics/{BOB}/t-b00000000002#t1",
        worked=True,
        finding="Вже проаналізовано.",
        cause="circumstances",
        closed_at=NOW - 49 * H,
        analyzed_at=NOW - 48 * H,
    )
    storage.write(
        "system", obs_path(BOB, "t-b00000000002", 1), present.model_dump_json().encode(), "application/json"
    )

    def tokens(llm: FakeLlm) -> list[str]:
        found = []
        for call in llm.calls:
            found += [w for w in call.text.split() if w.startswith("i3-")]
        return sorted(found)

    run1 = FakeLlm(fail={"i3-a2-s1": LlmUnavailable("down")})
    assert analyze(storage, run1, NOW) == AnalyzeReport(written=1, skipped=1, failed=1)
    assert tokens(run1) == ["i3-a1-s1", "i3-a2-s1"]

    run2 = FakeLlm()  # the same now: only the session that failed
    assert analyze(storage, run2, NOW) == AnalyzeReport(written=1, skipped=2, failed=0)
    assert tokens(run2) == ["i3-a2-s1"]

    # a lawful change between runs: a new closed session 2 in the first topic
    a1_s2 = S(2, [T(3, "user", "i3-a1-s2", NOW + 2 * H)], closed=NOW + 3 * H)
    write_topic(storage, ALICE, "t-a00000000001", [a1_s1, a1_s2])
    run3 = FakeLlm()  # thirty days later: the open session is closed now, the new one is new
    assert analyze(storage, run3, NOW + 30 * H24) == AnalyzeReport(written=2, skipped=3, failed=0)
    assert tokens(run3) == ["i3-a1-s2", "i3-b1-s1"]

    run4 = FakeLlm()  # and once more, later still: nothing
    assert analyze(storage, run4, NOW + 31 * H24) == AnalyzeReport(written=0, skipped=5, failed=0)
    assert run4.calls == []
