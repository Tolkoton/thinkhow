"""Contract tests of cards-library: the content of the 18 cards in the real `cards/` (Seam 5).
Slice tester; written from the contract, not the code."""

import hashlib
import re
from pathlib import Path
from typing import Any

import yaml
from cl_fakes import REPO_CARDS

from thinkhow.knowledge import Card, card_prompt

GOAL_IDS = [
    "first-principles", "issue-tree", "complexity-sensemaking", "five-whys", "is-is-not", "wrap-decision",
    "weighted-matrix", "reversible-doors", "evaporating-cloud", "pre-mortem", "consider-opposite",
    "socratic-questioning", "scamper", "mental-contrasting", "reflective-cycle", "goal-to-plan",
    "jobs-to-be-done", "opportunity-tree",
    # Task 307, product-cards «Goal» 1: «рівно 25 файлів: 18 id задачі 302 і 7 id вище» (objection 1).
    "customer-interviews", "demand-test", "positioning", "offer-design", "value-pricing", "traction-channels",
    "unit-economics",
]  # fmt: skip
NEW_IDS = [cid for cid in GOAL_IDS if cid != "pre-mortem"]  # every card but pre-mortem: 24 (product-cards I4)
TRADEMARKS = ["Kepner", "Cynefin", "WOOP", "GROW™", "Outcome-Driven", "Six Thinking Hats"]
FORBIDDEN = [r"час змінити метод", r"кризов", r"гаряч\w* лін", r"\b0800\b|\b11[26]\b|\+\d{6,}"]


def card_file(cid: str) -> Path:
    path = REPO_CARDS / f"{cid}.yaml"
    assert path.is_file(), f"cards/{cid}.yaml is missing"
    return path


def load(cid: str) -> Any:
    return yaml.safe_load(card_file(cid).read_text(encoding="utf-8"))


def strings(node: Any) -> list[str]:
    if isinstance(node, str):
        return [node]
    if isinstance(node, dict):
        return [s for value in node.values() for s in strings(value)]
    if isinstance(node, list):
        return [s for value in node for s in strings(value)]
    return []


def test_seam5_cards_holds_exactly_the_18_ids_of_the_goal() -> None:
    assert sorted(p.stem for p in REPO_CARDS.glob("*.yaml")) == sorted(GOAL_IDS)
    assert sorted(p.name for p in REPO_CARDS.iterdir() if p.is_file()) == sorted(
        f"{c}.yaml" for c in GOAL_IDS
    )


def test_seam5_every_card_is_valid_its_id_is_its_file_name_and_card_prompt_renders_it() -> None:
    for cid in GOAL_IDS:
        card = Card.model_validate(load(cid))
        assert card.id == cid
        assert card_prompt(card).strip(), cid


def test_seam5_the_last_trap_of_every_card_is_ne_toi_vypadok() -> None:
    for cid in GOAL_IDS:
        card = Card.model_validate(load(cid))
        assert card.facilitator.traps, cid
        assert card.facilitator.traps[-1].name == "Не той випадок", cid


def test_seam5_no_trademark_in_the_17_new_cards() -> None:
    for cid in NEW_IDS:
        texts = strings(load(cid))
        for text in texts:
            for mark in TRADEMARKS:
                assert mark.lower() not in text.lower(), (cid, mark, text)
            assert not re.search(r"\bODI\b", text), (cid, "ODI", text)


def test_seam5_no_change_method_phrase_and_no_crisis_text_in_the_17_new_cards() -> None:
    for cid in NEW_IDS:
        for text in strings(load(cid)):
            for pattern in FORBIDDEN:
                assert not re.search(pattern, text), (cid, pattern, text)


def test_seam5_pre_mortem_is_byte_for_byte_the_file_before_the_slice() -> None:
    data = (REPO_CARDS / "pre-mortem.yaml").read_bytes()
    blob = hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()
    assert blob == "8f52b66a795076cbe4e49965f8fb9b0b4009dd03"
