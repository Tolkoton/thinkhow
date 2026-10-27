"""DISPUTED tests of analysis-rules (questions Q1, Q2 to the contract): not sealed until the slice planner
answers. Each test takes one honest reading of a line the contract leaves open. Slice tester.
"""

from pathlib import Path

from ar_fakes import ALICE, CTX, NEW, NOW, H, M, SetLlm, d_choose, d_end, new_topic, seed_cards, talk

from thinkhow.learning.analyze import analyze
from thinkhow.platform.storage import LocalStorage


def test_disputed_q1_a_status_line_of_the_first_new_turn_stands_after_the_new_turns_header(
    tmp_path: Path,
) -> None:
    storage = LocalStorage(tmp_path / "b")
    seed_cards(storage, tmp_path)
    t0 = NOW - 3 * H
    ref = new_topic(storage, ALICE, t0 - M)
    talk(storage, ALICE, ref, 1, t0, {1: [d_choose(1, "alpha"), d_end(1, "alpha", "done")]})  # 1..2
    analyze(storage, SetLlm(), t0 + 10 * M)
    talk(storage, ALICE, ref, 1, t0 + 20 * M, first_no=3)  # 3..4; the end on 1 acts from #3
    llm = SetLlm()
    analyze(storage, llm, NOW)
    assert llm.calls[0].lines() == [
        CTX,
        "#1 людина: людина 1",
        "[Метод: Альфа (alpha)]",
        "#2 фасилітатор: фасилітатор 2",
        NEW,
        "[Метод закінчено: alpha — пройдено]",
        "#3 людина: людина 3",
        "#4 фасилітатор: фасилітатор 4",
    ]


def test_disputed_q2_a_card_without_a_title_is_written_as_its_id_alone(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path / "b")
    seed_cards(storage, tmp_path, {"alpha": "Альфа"})
    ref = new_topic(storage, ALICE, NOW - 2 * H)
    talk(storage, ALICE, ref, 1, NOW - H, {1: [d_choose(1, "zeta")]})
    llm = SetLlm()
    analyze(storage, llm, NOW)
    assert llm.calls[0].lines() == [
        "#1 людина: людина 1",
        "[Метод: zeta]",
        "#2 фасилітатор: фасилітатор 2",
    ]
