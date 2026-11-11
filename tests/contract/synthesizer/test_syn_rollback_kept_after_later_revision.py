"""Task 746 (overseer's test gap): a rollback that acted stays in the learner's text after a later revision
of the same id — the text reads the rollback's stored `changed`, not today's memory."""

from pathlib import Path

from syn_fakes import (
    HEADER,
    NOW,
    H,
    SynthLlm,
    answer,
    hand_apply,
    memory,
    note,
    ok_vet,
    one_obs,
    seeded,
    zero_measure,
)

from thinkhow.knowledge import rollback
from thinkhow.learning.synthesize import synthesize


def test_a_rolled_back_note_stays_under_its_header_after_a_later_revision_of_the_same_id(
    tmp_path: Path,
) -> None:
    storage = seeded(tmp_path)
    hand_apply(storage, upsert=[note("m-1", noticed="перша-версія-помічено")])
    bad = hand_apply(storage, upsert=[note("m-1", noticed="відкочене-помічено", do="відкочене-робити")])
    rollback(storage, bad, by="owner@example.com", now=NOW - 2 * H)  # m-1 back to the first version
    hand_apply(storage, upsert=[note("m-1", noticed="третя-версія-помічено")])
    assert memory(storage)["m-1"].noticed == "третя-версія-помічено"
    one_obs(storage, "tp-1", 1, "знахідка")
    llm = SynthLlm([answer()])

    synthesize(storage, llm, NOW, ok_vet, zero_measure)

    text = llm.calls[0].text
    assert HEADER in text
    after = text[text.index(HEADER) :]
    assert "відкочене-помічено" in after
    assert "відкочене-робити" in after
