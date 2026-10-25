"""Contract tests of research-live, the invariants I1–I2, each over hand-chosen inputs of its «Domain»
(slice tester; from the contract)."""

from rl_fakes import decision, item, live_module, llm_call, log_lines, research

from thinkhow.facilitation.types import ProblemMap

live = live_module()


def test_I1_each_answers_evidence_belongs_to_that_answer() -> None:
    # Answer 18: the router chose a card on the person's #17, a quick search for #18.
    r17 = [decision(17, "choose", "weighted-matrix")]
    e18 = live.evidence(18, [], r17, [research(18)], log_lines(llm_call(900), llm_call(2000, 2)))
    assert e18.turn == 18
    assert e18.decisions == [decision(17, "choose", "weighted-matrix")]
    assert e18.research == [research(18)]
    assert e18.calls == [llm_call(900), llm_call(2000, 2)]

    # Answer 20: with a card, no new decision; research.json keeps #18's entry and adds #20's.
    e20 = live.evidence(
        20, r17, list(r17), [research(18), research(20, "deep")], log_lines(llm_call(3000, 4))
    )
    assert e20.decisions == []
    assert e20.research == [research(20, "deep")]
    assert e20.calls == [llm_call(3000, 4)]

    # Answer 22: no search at all — the earlier entries (one of them numbered 21, the person's turn) stay out.
    e22 = live.evidence(22, r17, list(r17), [research(18), research(20, "deep"), research(21)], log_lines())
    assert e22.decisions == []
    assert e22.research == []
    assert e22.calls == []

    # Answer 24: a new decision after earlier ones (the card ended, the router offered anew on #23).
    r23 = [*r17, decision(23, "offer", None)]
    e24 = live.evidence(
        24, r17, r23, [research(18), research(20, "deep"), research(24)], log_lines(llm_call(10))
    )
    assert e24.decisions == [decision(23, "offer", None)]
    assert e24.research == [research(24)]


def test_I2_start_map_is_exactly_the_items_with_turn_number_at_most_16() -> None:
    items = [
        item("i1", "t1"),
        item("i3", "t3", "router_note"),
        item("i5", "t5"),
        item("i10", "t7", "router_note"),
        item("i9", "t9"),
        item("i12", "t10"),
        item("i15", "t15"),
        item("i16", "t16"),
        item("i17", "t17"),
        item("i19", "t19"),
        item("i2", "t2"),
        item("i29", "t29"),
        item("i30", "t30"),
        item("i100", "t100"),
    ]
    got = live.start_map(ProblemMap(items=items, phase_id=None, last_turn=30))
    assert {i.id: i for i in got.items} == {
        i.id: i for i in items if i.id in {"i1", "i3", "i5", "i10", "i9", "i12", "i15", "i16", "i2"}
    }
    assert len(got.items) == 9

    # The empty map stays empty; a map with nothing after 16 keeps all its items.
    assert live.start_map(ProblemMap(items=[], phase_id=None, last_turn=0)).items == []
    early = [item("i3", "t3", "router_note"), item("i16", "t16")]
    assert {i.id for i in live.start_map(ProblemMap(items=early, phase_id=None, last_turn=16)).items} == {
        "i3",
        "i16",
    }
