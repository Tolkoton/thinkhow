"""Contract tests of deep-change-question through `workspace.reply` on `LocalStorage`, hardest seam 1: the
refined question of a change reaches the report through the saved proposal `deep_pending.json` (slice
tester; from the contract, not the code). Every answer reads the topic through a new storage object."""

from pathlib import Path

from dcq_fakes import (
    CHANGE,
    CHANGE_AGAIN,
    DQ2,
    PROPOSAL_2_DQ2,
    PROPOSAL_4_DQ2,
    dc,
    file_of,
    plan_with,
)

from thinkhow.workspace import Answered

YES = "Так, запускай."


def test_seam1_the_refined_question_is_shown_saved_and_researched_after_yes(tmp_path: Path) -> None:
    # chain A: proposal with DQ -> a change, the plan gives DQ2 -> «так»
    a = tmp_path / "a"
    ref = dc.new_topic(a)
    dc.propose_on_router(a, ref)
    llm = dc.DcLlm(consents=[dc.consent_raw("change")], plans=[plan_with(dc.INTRO_2, dc.PLAN_2, DQ2)])
    got, shown = dc.say(a, dc.fac(llm), ref, CHANGE)
    assert got[-1] == Answered(4), got[-1]
    assert shown == PROPOSAL_2_DQ2
    assert DQ2 in shown and dc.DQ not in shown
    assert dc.pending_file(a, ref) == {"turn": 4, "pending": file_of(DQ2, dc.INTRO_2, dc.PLAN_2)}
    yes = dc.agree_llm()
    got, _ = dc.say(a, dc.fac(yes), ref, YES)
    assert got[-1] == Answered(6), got[-1]
    assert "[Питання людини]\n" + DQ2 in yes.of("report")[0].text
    entries = dc.rq.read_research(dc.store_at(a), ref)
    assert entries is not None and [(e["depth"], e["question"]) for e in entries] == [("deep", DQ2)]

    # chain B: the same, then one more change whose plan has no question -> DQ2 stays -> «так»
    b = tmp_path / "b"
    ref = dc.new_topic(b)
    dc.propose_on_router(b, ref)
    first = dc.DcLlm(consents=[dc.consent_raw("change")], plans=[plan_with(dc.INTRO_2, dc.PLAN_2, DQ2)])
    got, _ = dc.say(b, dc.fac(first), ref, CHANGE)
    assert got[-1] == Answered(4), got[-1]
    second = dc.DcLlm(consents=[dc.consent_raw("change")], plans=[dc.PLAN_RAW_4])
    got, shown = dc.say(b, dc.fac(second), ref, CHANGE_AGAIN)
    assert got[-1] == Answered(6), got[-1]
    assert shown == PROPOSAL_4_DQ2
    assert dc.pending_file(b, ref) == {"turn": 6, "pending": file_of(DQ2, dc.INTRO_4, dc.PLAN_4)}
    yes = dc.agree_llm()
    got, _ = dc.say(b, dc.fac(yes), ref, YES)
    assert got[-1] == Answered(8), got[-1]
    assert "[Питання людини]\n" + DQ2 in yes.of("report")[0].text
    entries = dc.rq.read_research(dc.store_at(b), ref)
    assert entries is not None and [(e["depth"], e["question"]) for e in entries] == [("deep", DQ2)]
