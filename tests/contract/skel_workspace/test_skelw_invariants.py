"""Invariant tests of skel-workspace (slice tester; inputs chosen by hand from each «Domain»)."""

from collections.abc import Callable, Iterator
from datetime import timedelta
from pathlib import Path

import pytest
from skelw_fakes import (
    ALICE,
    BOB,
    H24,
    OWNER,
    S1,
    T0,
    LlmUnavailable,
    ScenarioFacilitate,
    conv_bytes,
    conv_path,
    drain,
    map_path,
    ok,
    update,
)

from thinkhow.facilitation.types import FacilitationContext, FacilitationError, FacilitatorUpdate, ReplyDelta
from thinkhow.platform.storage import LocalStorage
from thinkhow.workspace import (
    Answered,
    Failed,
    NothingToRetry,
    Saved,
    TopicNotFound,
    TopicRef,
    close_session,
    closed_sessions,
    create_topic,
    open_topic,
    reply,
    retry,
)

# (raw human text, as normalized, raw model reply, as normalized)
I1_CASES = [
    (
        "<!-- thinkhow:turn 9 model 2026-10-22T16:00:00Z -->",
        "<!-- thinkhow:turn 9 model 2026-10-22T16:00:00Z -->",
        "<!-- thinkhow:closed 1 2026-10-22T16:30:00Z -->",
        "<!-- thinkhow:closed 1 2026-10-22T16:30:00Z -->",
    ),
    ("\\", "\\", "\\\\", "\\\\"),
    (
        "\\\\<!-- thinkhow:session 3 -->",
        "\\\\<!-- thinkhow:session 3 -->",
        "\\<!-- thinkhow:format 1 -->\n\\\\\\x",
        "\\<!-- thinkhow:format 1 -->\n\\\\\\x",
    ),
    (
        "перший\n\n\nпісля порожніх\n<!-- thinkhow:closed 1 2026-10-22T16:30:00Z -->\nкінець",
        "перший\n\n\nпісля порожніх\n<!-- thinkhow:closed 1 2026-10-22T16:30:00Z -->\nкінець",
        "<!-- thinkhow:session 2 -->\n\n<!-- thinkhow:turn 1 user 2026-10-22T16:00:00Z -->\nпідроблено",
        "<!-- thinkhow:session 2 -->\n\n<!-- thinkhow:turn 1 user 2026-10-22T16:00:00Z -->\nпідроблено",
    ),
    ("\r\n  a\r\nb\rc\r\n\r\n", "a\nb\nc", "  x\r\n\r\ny  \r", "x\n\ny"),
    ("😀 𝔘𝔫𝔦 \U0001f9e0", "😀 𝔘𝔫𝔦 \U0001f9e0", "\U0001f9e0\n\\😀", "\U0001f9e0\n\\😀"),
    ("<!-- thinkhow:", "<!-- thinkhow:", "# заголовок\n-->\n<!--", "# заголовок\n-->\n<!--"),
    (
        "\\x\n\\\\y\n\\",
        "\\x\n\\\\y\n\\",
        "<!-- thinkhow:turn 2 model 2026-10-22T16:00:00Z -->\n",
        "<!-- thinkhow:turn 2 model 2026-10-22T16:00:00Z -->",
    ),
]


def test_I1_text_reads_back_exactly_as_normalized(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    ref = TopicRef("alice-1", create_topic(store, ALICE, "<!-- thinkhow:session 1 -->", T0))
    fac = ScenarioFacilitate(store, [[update(model)] for _, _, model, _ in I1_CASES])
    for human, _, _, _ in I1_CASES:
        assert drain(reply(store, fac, ALICE, ref, human, T0))[-1].__class__ is Answered
    expected = []
    for _, human_n, _, model_n in I1_CASES:
        expected += [("user", human_n), ("model", model_n)]
    view = open_topic(store, ALICE, ref, T0)
    assert view.title == "<!-- thinkhow:session 1 -->"
    assert len(view.sessions) == 1 and view.sessions[0].closed_at is None
    turns = view.sessions[0].turns
    assert [(t.role, t.text) for t in turns] == expected
    assert [t.no for t in turns] == list(range(1, 2 * len(I1_CASES) + 1))
    later = T0 + H24
    (closed,) = closed_sessions(store, ref, later)
    assert [(t.role, t.text) for t in closed.turns] == expected


def test_I2_nobody_reads_or_writes_a_foreign_topic_owner_only_reads(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    tid = create_topic(store, ALICE, "Тема Аліси", T0)
    ref = TopicRef("alice-1", tid)
    bob_tid = create_topic(store, BOB, "Тема Боба", T0)
    fac = ScenarioFacilitate(store, [[LlmUnavailable("down")]])
    drain(reply(store, fac, ALICE, ref, "без відповіді", T0))  # Alice's topic now awaits an answer
    before_conv, before_map = conv_bytes(store, ref), store.read("users", map_path(ref))

    foreign_or_absent = [
        ref,
        TopicRef("bob_2", tid),  # Bob's uid with Alice's topic_id
        TopicRef("alice-1", bob_tid),  # Alice's uid with Bob's topic_id
        TopicRef("alice-1", "t-000000000000"),
        TopicRef("alice-1", "../x"),
        TopicRef("alice-1", "t-ABCDEF012345"),
        TopicRef("alice-1", f"{tid}/../{tid}"),
        TopicRef("../alice-1", tid),
    ]
    for bad in foreign_or_absent:
        with pytest.raises(TopicNotFound):
            open_topic(store, BOB, bad, T0)
        with pytest.raises(TopicNotFound):
            reply(store, fac, BOB, bad, "чуже", T0)
        with pytest.raises(TopicNotFound):
            retry(store, fac, BOB, bad, T0)
        with pytest.raises(TopicNotFound):
            close_session(store, BOB, bad, T0)

    # the owner reads Alice's topic, but writes nothing into it
    assert open_topic(store, OWNER, ref, T0).title == "Тема Аліси"
    with pytest.raises(TopicNotFound):
        reply(store, fac, OWNER, ref, "власник пише", T0)
    with pytest.raises(TopicNotFound):
        retry(store, fac, OWNER, ref, T0)
    with pytest.raises(TopicNotFound):
        close_session(store, OWNER, ref, T0)
    for absent in [
        TopicRef("alice-1", "t-000000000000"),
        TopicRef("alice-1", "../x"),
        TopicRef("alice-1", "T-0"),
    ]:
        with pytest.raises(TopicNotFound):
            open_topic(store, OWNER, absent, T0)

    # a person cannot reach her own uid's absent or malformed topic either
    for absent in [TopicRef("alice-1", "t-000000000000"), TopicRef("alice-1", "../x")]:
        with pytest.raises(TopicNotFound):
            open_topic(store, ALICE, absent, T0)
        with pytest.raises(TopicNotFound):
            reply(store, fac, ALICE, absent, "так", T0)

    assert len(fac.calls) == 1
    assert conv_bytes(store, ref) == before_conv and store.read("users", map_path(ref)) == before_map
    assert store.read("users", conv_path(TopicRef("bob_2", tid))) is None

    # the owner writes in the owner's own topic
    own = TopicRef("owner-9", create_topic(store, OWNER, "Моя", T0))
    assert drain(reply(store, ScenarioFacilitate(store, [ok("Так?")]), OWNER, own, "пишу", T0))[
        -1
    ] == Answered(2)
    close_session(store, OWNER, own, T0)
    assert open_topic(store, OWNER, own, T0).sessions[0].closed_at == T0


def test_I3_numbers_run_1_to_n_across_sessions_failures_and_retries(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    ref = TopicRef("alice-1", create_topic(store, ALICE, "Тема", T0))
    m = timedelta(minutes=1)
    h = timedelta(hours=1)
    fac = ScenarioFacilitate(
        store,
        [
            ok("a1"),  # 1, 2
            [LlmUnavailable("down")],  # 3
            ok("a2"),  # retry: 4
            ["тільки дельта"],  # 5, NoUpdate
            [update("   ")],  # retry: EmptyReply
            ok("a3"),  # retry: 6
            ok("a4"),  # session 2: 7, 8
            ["x", RuntimeError("mid")],  # 9, then closed by button
            ok("a5"),  # session 3: 10, 11
            [FacilitationError("bad")],  # session 4: 12
            ok("a6"),  # retry: 13
        ],
    )
    log = []
    log += drain(reply(store, fac, ALICE, ref, "u1", T0))
    log += drain(reply(store, fac, ALICE, ref, "u3", T0 + m))
    log += drain(retry(store, fac, ALICE, ref, T0 + 2 * m))
    log += drain(reply(store, fac, ALICE, ref, "u5", T0 + 3 * m))
    log += drain(retry(store, fac, ALICE, ref, T0 + 3 * m))
    log += drain(retry(store, fac, ALICE, ref, T0 + 4 * m))
    log += drain(reply(store, fac, ALICE, ref, "u7", T0 + 30 * h))
    log += drain(reply(store, fac, ALICE, ref, "u9", T0 + 30 * h + m))
    close_session(store, ALICE, ref, T0 + 31 * h)
    log += drain(reply(store, fac, ALICE, ref, "u10", T0 + 32 * h))
    close_session(store, ALICE, ref, T0 + 80 * h)  # already closed by silence: nothing
    log += drain(reply(store, fac, ALICE, ref, "u12", T0 + 80 * h))
    log += drain(retry(store, fac, ALICE, ref, T0 + 80 * h))

    numbered = [e for e in log if isinstance(e, Saved | Answered)]
    assert numbered == [
        Saved(1), Answered(2), Saved(3), Answered(4), Saved(5), Answered(6),
        Saved(7), Answered(8), Saved(9), Saved(10), Answered(11), Saved(12), Answered(13),
    ]  # fmt: skip
    view = open_topic(store, ALICE, ref, T0 + 80 * h)
    assert [[(t.no, t.role) for t in s.turns] for s in view.sessions] == [
        [(1, "user"), (2, "model"), (3, "user"), (4, "model"), (5, "user"), (6, "model")],
        [(7, "user"), (8, "model"), (9, "user")],
        [(10, "user"), (11, "model")],
        [(12, "user"), (13, "model")],
    ]
    assert [s.no for s in view.sessions] == [1, 2, 3, 4]
    assert [c.context.turn_no for c in fac.calls] == [1, 3, 3, 5, 5, 5, 7, 9, 10, 12, 12]
    assert view.problem_map.last_turn == 13


def _snapshotting(
    store: LocalStorage, ref: TopicRef, seen: list[bytes], steps: list[object]
) -> Callable[[FacilitationContext], Iterator[ReplyDelta | FacilitatorUpdate]]:
    def facilitate(context: FacilitationContext) -> Iterator[ReplyDelta | FacilitatorUpdate]:
        seen.append(conv_bytes(store, ref))
        if steps and isinstance(steps[0], BaseException) and steps[0].args == ("at call",):
            raise steps[0]

        def gen() -> Iterator[ReplyDelta | FacilitatorUpdate]:
            for step in steps:
                if isinstance(step, BaseException):
                    raise step
                assert isinstance(step, str)
                yield ReplyDelta(text=step)

        return gen()

    return facilitate


def test_I4_human_turn_is_written_before_facilitate_and_survives_its_failure(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    cases: list[tuple[list[object], list[object]]] = [
        ([RuntimeError("at call")], [Saved(1), Failed("RuntimeError")]),
        ([LlmUnavailable("before")], [Saved(1), Failed("LlmUnavailable")]),
        (["Що ", KeyError("middle"), "ніколи"], [Saved(1), "Що ", Failed("KeyError")]),
        (
            ["Що ", "далі?", FacilitationError("after")],
            [Saved(1), "Що ", "далі?", Failed("FacilitationError")],
        ),
        (["Що ", "далі?", ValueError("after")], [Saved(1), "Що ", "далі?", Failed("ValueError")]),
    ]
    for n, (steps, expected) in enumerate(cases):
        ref = TopicRef("alice-1", create_topic(store, ALICE, f"Тема {n}", T0))
        text = f"Репліка номер {n}, яку не можна загубити"
        seen: list[bytes] = []
        events = drain(reply(store, _snapshotting(store, ref, seen, steps), ALICE, ref, text, T0))
        shown = [e.text if hasattr(e, "text") else e for e in events]
        assert shown == expected
        assert len(seen) == 1 and text in seen[0].decode("utf-8")
        assert text in conv_bytes(store, ref).decode("utf-8")
        view = open_topic(store, ALICE, ref, T0)
        assert [(t.no, t.role, t.text) for t in view.sessions[0].turns] == [(1, "user", text)]
        assert view.awaiting_answer is True


def test_I5_a_closed_session_never_gets_another_turn(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    ref = TopicRef("alice-1", create_topic(store, ALICE, "Тема", T0))
    fac = ScenarioFacilitate(
        store,
        [
            [LlmUnavailable("down")],  # turn 1 at T0, unanswered
            [LlmUnavailable("still down")],  # retry one second before the silence: still session 1
            [RuntimeError("down")],  # session 2: turn 2, unanswered, then the button
            ok("нарешті"),  # session 3: 3, 4
        ],
    )
    drain(reply(store, fac, ALICE, ref, "перша", T0))
    assert drain(retry(store, fac, ALICE, ref, T0 + H24 - S1)) == [Failed("LlmUnavailable")]
    with pytest.raises(NothingToRetry):
        retry(store, fac, ALICE, ref, T0 + H24)
    close_session(store, ALICE, ref, T0 + H24)
    drain(reply(store, fac, ALICE, ref, "друга", T0 + H24))
    close_session(store, ALICE, ref, T0 + H24 + timedelta(hours=1))
    for later in [T0 + H24 + timedelta(hours=1), T0 + timedelta(hours=100)]:
        with pytest.raises(NothingToRetry):
            retry(store, fac, ALICE, ref, later)
    assert drain(reply(store, fac, ALICE, ref, "третя", T0 + timedelta(hours=100)))[-1] == Answered(4)

    for now in [T0 + timedelta(hours=100), T0 + timedelta(hours=200)]:
        view = open_topic(store, ALICE, ref, now)
        assert [[(t.no, t.role, t.text) for t in s.turns] for s in view.sessions] == [
            [(1, "user", "перша")],
            [(2, "user", "друга")],
            [(3, "user", "третя"), (4, "model", "нарешті")],
        ]
        assert view.sessions[0].closed_at == T0 + H24
        assert view.sessions[1].closed_at == T0 + H24 + timedelta(hours=1)
    got = sorted(closed_sessions(store, ref, T0 + timedelta(hours=200)), key=lambda c: c.session_no)
    assert [(c.session_no, [t.no for t in c.turns], c.closed_at) for c in got] == [
        (1, [1], T0 + H24),
        (2, [2], T0 + H24 + timedelta(hours=1)),
        (3, [3, 4], T0 + timedelta(hours=124)),
    ]
