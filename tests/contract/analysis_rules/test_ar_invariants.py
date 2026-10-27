"""Invariant tests of analysis-rules (learning-loop S2): I1-I4 of the contract, inputs chosen by hand from
each Domain. Slice tester; from the contract, not the code.
"""

from pathlib import Path
from typing import Any

from ar_fakes import (
    ALICE,
    BOB,
    DAY,
    NOW,
    H,
    M,
    SetLlm,
    d_answer,
    d_ask,
    d_choose,
    d_end,
    d_offer,
    new_topic,
    obs,
    obs_names,
    one,
    put_raw,
    say,
    seed_cards,
    talk,
)

from thinkhow.facilitation.types import Decision
from thinkhow.learning.analyze import AnalyzeReport, analyze
from thinkhow.learning.observations import read_all
from thinkhow.platform.llm import LlmUnavailable
from thinkhow.platform.storage import LocalStorage
from thinkhow.workspace import TopicRef, reply


class _Down:
    """A `Facilitate` whose model fails: the person's turn stays without an answer."""

    def __call__(self, context: Any) -> Any:
        raise RuntimeError("down")


def _range_files(storage: LocalStorage, ref: TopicRef) -> list[dict[str, Any]]:
    return [obs(storage, ref, n) for n in sorted(obs_names(storage, ref))]


def _check_I1(storage: LocalStorage, ref: TopicRef) -> None:
    for f in _range_files(storage, ref):
        for o in f["observations"]:
            assert f["first_turn"] <= o["turn"] <= f["last_turn"], (f, o)
            assert o["link"].endswith(f"#t{o['turn']}"), o


def test_I1_every_anchor_is_a_new_turn(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path / "b")
    t0 = NOW - 3 * DAY
    # (b) context before the new turns: the list index is not the turn number
    ctx = new_topic(storage, BOB, t0 - M)
    talk(storage, BOB, ctx, 2, t0)  # 1..4
    analyze(storage, SetLlm(), t0 + H)
    talk(storage, BOB, ctx, 2, t0 + 2 * H, first_no=5)  # 5..8, same session
    # (a) one unanswered turn: both edges of the range are the same turn
    single = new_topic(storage, ALICE, t0 + 2 * H)
    list(reply(storage, _Down(), ALICE, single, "людина 1", t0 + 2 * H + M))
    # the first and the last new turn, a repeat, out of order
    plan = {
        "single": lambda anchors: [one(anchors[0]), one(anchors[-1])],
        "ctx": lambda anchors: [one(anchors[-1]), one(anchors[0]), one(anchors[0])],
    }

    def answer(anchors: list[str]) -> list[dict[str, Any]]:
        return plan["single" if anchors == ["t1"] else "ctx"](anchors)

    assert analyze(storage, SetLlm(plan=answer), t0 + 3 * H) == AnalyzeReport(written=2, skipped=0, failed=0)
    assert [o["turn"] for o in obs(storage, single, "t1-t1.json")["observations"]] == [1, 1]
    assert [o["turn"] for o in obs(storage, ctx, "t5-t8.json")["observations"]] == [8, 5, 5]

    # (c) a lawful run after a refused one: the same turns come again, then after a new session
    again = new_topic(storage, ALICE, t0 - M)
    talk(storage, ALICE, again, 1, t0)  # 1..2
    assert analyze(storage, SetLlm(fail_all=LlmUnavailable("down")), t0 + 3 * H + M).failed == 1
    say(storage, ALICE, again, "людина 3", "фасилітатор 4", t0 + DAY + H)  # a new session
    assert analyze(storage, SetLlm(plan=lambda a: [one(x) for x in a]), t0 + DAY + 2 * H).written >= 1
    assert sorted(obs_names(storage, again)) == ["t1-t4.json"]
    assert [o["turn"] for o in obs(storage, again, "t1-t4.json")["observations"]] == [1, 2, 3, 4]

    for ref in (single, ctx, again):
        _check_I1(storage, ref)


def test_I2_ids_are_unique_across_read_all_and_stable_between_two_calls(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path / "b")
    seed_cards(storage, tmp_path)
    t0 = NOW - 5 * H
    # new sets written by the analyzer: two runs in one topic, two observations each (k within the file)
    ref = new_topic(storage, ALICE, t0 - M)
    talk(storage, ALICE, ref, 1, t0)
    two = SetLlm(plan=lambda a: [one(a[0]), one(a[-1])])
    analyze(storage, two, t0 + H)
    talk(storage, ALICE, ref, 1, t0 + 2 * H, first_no=3)
    analyze(storage, two, t0 + 3 * H)
    # old files of every shape in another topic of another person, side by side with a new one
    old_t = """{"uid":"bob_2","topic_id":"zzz999","first_turn":1,"last_turn":2,"turn":2,\
"link":"/topics/bob_2/zzz999#t2","worked":true,"finding":"крок","cause":"method",\
"analyzed_at":"2026-10-24T04:00:00Z"}"""
    old_s = """{"uid":"bob_2","topic_id":"zzz999","session_no":1,"turn":1,"link":"/topics/bob_2/zzz999#t1",\
"worked":false,"finding":"сесія","cause":"facilitation","closed_at":"2026-10-22T03:00:00Z",\
"analyzed_at":"2026-10-22T04:00:00Z"}"""
    put_raw(storage, "bob_2", "zzz999", "t1-t2.json", old_t)
    put_raw(storage, "bob_2", "zzz999", "s1.json", old_s)

    first = [o.id for o in read_all(storage)]
    second = [o.id for o in read_all(storage)]
    assert first == second
    assert len(first) == len(set(first))
    base = f"{ALICE.id}/{ref.topic_id}"
    assert set(first) == {
        f"{base}/t1-t2/1",
        f"{base}/t1-t2/2",
        f"{base}/t3-t4/1",
        f"{base}/t3-t4/2",
        "bob_2/zzz999/t1-t2/1",
        "bob_2/zzz999/s1/1",
    }


def test_I3_the_set_is_whole_count_and_order_of_the_answer(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path / "b")
    t0 = NOW - 3 * H
    answers: dict[str, list[dict[str, Any]]] = {
        "n1": [one("t2", kind="progress", cause="router", worked=True)],
        "n3": [
            one("t4", kind="stuck", cause="facilitation"),
            one("t1", kind="method_fit", cause="method"),
            one("t4", kind="progress", cause="circumstances", worked=True),
        ],
        "n7": [one(a, kind="stuck", cause="router") for a in ("t6", "t1", "t2", "t3", "t2", "t5", "t4")],
    }
    refs = {}
    for i, key in enumerate(answers):
        user = ALICE if i % 2 == 0 else BOB
        ref = new_topic(storage, user, t0 - M, title=key)
        n_pairs = {"n1": 1, "n3": 2, "n7": 3}[key]
        talk(storage, user, ref, n_pairs, t0)
        refs[key] = ref
    by_size = {2: "n1", 4: "n3", 6: "n7"}

    def answer(anchors: list[str]) -> list[dict[str, Any]]:
        return answers[by_size[len(anchors)]]

    assert analyze(storage, SetLlm(plan=answer), NOW) == AnalyzeReport(written=3, skipped=0, failed=0)
    expected_turns = {"n1": [2], "n3": [4, 1, 4], "n7": [6, 1, 2, 3, 2, 5, 4]}
    expected_kinds = {
        "n1": ["progress"],
        "n3": ["stuck", "method_fit", "progress"],
        "n7": ["stuck"] * 7,
    }
    expected_causes = {
        "n1": ["router"],
        "n3": ["facilitation", "method", "circumstances"],
        "n7": ["router"] * 7,
    }
    for key, ref in refs.items():
        (name,) = obs_names(storage, ref)
        got = obs(storage, ref, name)["observations"]
        assert [o["turn"] for o in got] == expected_turns[key], key
        assert [o["kind"] for o in got] == expected_kinds[key], key
        assert [o["cause"] for o in got] == expected_causes[key], key
        stem = name.removesuffix(".json")
        assert [o["id"] for o in got] == [
            f"{ref.uid}/{ref.topic_id}/{stem}/{k}" for k in range(1, len(expected_turns[key]) + 1)
        ], key


def test_I4_card_id_is_the_card_that_led_the_anchor_turn(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path / "b")
    seed_cards(storage, tmp_path)
    t0 = NOW - 3 * H
    cases: list[tuple[str, dict[int, list[Decision]], int, list[str | None]]] = [
        # offer, choose, end done, choose and end on one turn, then ask
        (
            "long",
            {
                1: [d_offer(1, "alpha", "beta")],
                3: [d_choose(3, "alpha")],
                5: [d_end(5, "alpha", "done")],
                7: [d_choose(7, "beta"), d_end(7, "beta", "not_fit")],
                11: [d_ask(11)],
            },
            6,
            [None, None, None, "alpha", "alpha", "alpha", None, "beta", None, None, None, None],
        ),
        # end, then the router chooses again on the person's next turn
        (
            "end-choose",
            {1: [d_choose(1, "alpha")], 3: [d_end(3, "alpha", "not_fit")], 5: [d_choose(5, "beta")]},
            3,
            [None, "alpha", "alpha", "alpha", None, "beta"],
        ),
        # a choose on the first turn, then a fact answer
        (
            "answer",
            {1: [d_choose(1, "gamma")], 3: [d_answer(3)]},
            3,
            [None, "gamma", "gamma", None, None, None],
        ),
        # a card ends on the turn it was chosen, the router offers on the next
        (
            "choose-end",
            {
                1: [d_offer(1, "alpha", "gamma")],
                3: [d_choose(3, "gamma"), d_end(3, "gamma", "done")],
                5: [d_offer(5, "beta")],
            },
            3,
            [None, None, None, "gamma", None, None],
        ),
    ]
    refs = {}
    for name, plan, pairs, _ in cases:
        ref = new_topic(storage, ALICE, t0 - M, title=name)
        talk(storage, ALICE, ref, pairs, t0, plan)
        refs[name] = ref
    # the model's answer cannot move card_id: every anchor, in reverse order
    llm = SetLlm(plan=lambda anchors: [one(a) for a in reversed(anchors)])
    assert analyze(storage, llm, NOW) == AnalyzeReport(written=4, skipped=0, failed=0)
    for name, _, pairs, expected in cases:
        (fname,) = obs_names(storage, refs[name])
        got = obs(storage, refs[name], fname)["observations"]
        by_turn = {o["turn"]: o["card_id"] for o in got}
        assert [by_turn[n] for n in range(1, 2 * pairs + 1)] == expected, name
