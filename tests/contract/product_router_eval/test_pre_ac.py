"""The AC test of slice product-router-eval (Goal 6): the newest `router-eval` report, the newest
`.compare.md` and the 7 live conversations of the new cards. Slice tester; written from the contract.

«Newest» is the last name in sorted order: the files are named by the run's time `X` (Seam), as the
sealed `ac4` of task 302 reads them.
"""

from pathlib import Path

from pre_helpers import ARTIFACTS, NEW_CARDS, card_has_row, card_passes

EVAL = ARTIFACTS / "router-eval"
CONVERSATIONS = ARTIFACTS / "card-conversations"


def _newest_report() -> Path:
    reports = sorted(p for p in EVAL.glob("*.md") if not p.name.endswith(".compare.md"))
    assert reports, EVAL
    return reports[-1]


def test_ac_newest_report_has_a_line_for_each_new_card_and_the_word_confusions() -> None:
    text = _newest_report().read_text(encoding="utf-8")
    lines = text.splitlines()
    missing = [card for card in NEW_CARDS if not any(card in ln for ln in lines)]
    assert not missing, (_newest_report().name, missing)
    assert "плутанин" in text.lower(), _newest_report().name


def test_ac_newest_json_has_its_compare_md_with_old_and_new_sections() -> None:
    runs = sorted(EVAL.glob("*.json"))
    assert runs, EVAL
    compare_md = runs[-1].with_name(runs[-1].stem + ".compare.md")
    assert compare_md.is_file(), compare_md.name
    text = compare_md.read_text(encoding="utf-8")
    assert "Старі випадки" in text
    assert "Нові випадки" in text


def test_ac_each_new_card_chosen_and_done_in_its_newest_conversation_folder() -> None:
    folders = sorted(p for p in CONVERSATIONS.iterdir() if (p / "index.md").is_file())
    failed = []
    for card in NEW_CARDS:
        mine = [f for f in folders if card_has_row((f / "index.md").read_text(encoding="utf-8"), card)]
        if not mine or not card_passes((mine[-1] / "index.md").read_text(encoding="utf-8"), card):
            failed.append((card, mine[-1].name if mine else None))
    assert not failed, failed
