"""Contract tests of research-live: the owner's turns, the start map and one answer's evidence
(slice tester; from the contract, not the code)."""

from rl_fakes import (
    decision,
    item,
    live_module,
    llm_call,
    log_lines,
    owner_conversation,
    research,
    turn,
)

from thinkhow.facilitation.types import ProblemMap
from thinkhow.workspace import conversation as conv_file

live = live_module()


def test_owner_turns_are_the_persons_turns_after_16_in_order() -> None:
    conv = owner_conversation()
    got = live.owner_turns(conv)
    assert [t.no for t in got] == [17, 19, 21, 23, 25, 27, 29]
    assert all(t.role == "user" for t in got)
    assert got == [turn(n, "user") for n in (17, 19, 21, 23, 25, 27, 29)]


def test_owner_turns_leave_out_a_persons_turn_numbered_16() -> None:
    turns = [turn(14, "model"), turn(15, "model"), turn(16, "user"), turn(17, "model"), turn(18, "user")]
    conv = conv_file.Conversation(title="x", sessions=[conv_file.SessionDoc(no=1, turns=turns)])
    assert [t.no for t in live.owner_turns(conv)] == [18]


def test_start_map_has_no_phase_and_last_turn_16() -> None:
    bucket = ProblemMap(items=[item("i1", "t1"), item("i30", "t29")], phase_id=None, last_turn=30)
    got = live.start_map(bucket)
    assert got.phase_id is None
    assert got.last_turn == 16
    assert got.items == [item("i1", "t1")]


def test_evidence_decisions_are_routing_json_new_tail() -> None:
    before = [decision(17, "offer", None)]
    after = [decision(17, "offer", None), decision(19, "choose", "premortem")]
    got = live.evidence(20, before, after, [], "")
    assert got.turn == 20
    assert got.decisions == [decision(19, "choose", "premortem")]


def test_evidence_without_a_new_decision_has_none() -> None:
    routing = [decision(17)]
    got = live.evidence(22, list(routing), list(routing), [], "")
    assert got.decisions == []


def test_evidence_research_is_entries_with_this_answers_turn() -> None:
    entries = [research(18), research(20, "deep", "ринок вживаних авто"), research(22)]
    got = live.evidence(20, [], [], entries, "")
    assert got.research == [research(20, "deep", "ринок вживаних авто")]


def test_evidence_calls_are_this_outputs_llm_call_lines() -> None:
    other = {"severity": "INFO", "event": "seed_done", "created": 3, "request_id": None}
    text = log_lines(llm_call(1200), other, llm_call(5400, queries=3))
    got = live.evidence(18, [], [], [], text)
    assert got.calls == [llm_call(1200), llm_call(5400, queries=3)]
