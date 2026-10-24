"""Disputed contract test of cards-library (Q1): the bans of Seam 5 that the contract does not mark
«регістронезалежно» (`\\bODI\\b`, «час змінити метод», `кризов`, `гаряч\\w* лін`) read case-insensitively,
so that «Кризова…» or «Час змінити метод» at the start of a sentence is caught too.
Not sealed until answered."""

import re
from typing import Any

import yaml
from cl_fakes import REPO_CARDS

GOAL_IDS = [
    "first-principles", "issue-tree", "complexity-sensemaking", "five-whys", "is-is-not", "wrap-decision",
    "weighted-matrix", "reversible-doors", "evaporating-cloud", "pre-mortem", "consider-opposite",
    "socratic-questioning", "scamper", "mental-contrasting", "reflective-cycle", "goal-to-plan",
    "jobs-to-be-done", "opportunity-tree",
]  # fmt: skip
NEW_IDS = [cid for cid in GOAL_IDS if cid != "pre-mortem"]
PATTERNS = [r"\bODI\b", r"час змінити метод", r"кризов", r"гаряч\w* лін"]


def strings(node: Any) -> list[str]:
    if isinstance(node, str):
        return [node]
    if isinstance(node, dict):
        return [s for value in node.values() for s in strings(value)]
    if isinstance(node, list):
        return [s for value in node for s in strings(value)]
    return []


def test_q1_seam5_bans_without_a_case_rule_also_hold_case_insensitively_in_the_17_new_cards() -> None:
    for cid in NEW_IDS:
        path = REPO_CARDS / f"{cid}.yaml"
        assert path.is_file(), f"cards/{cid}.yaml is missing"
        for text in strings(yaml.safe_load(path.read_text(encoding="utf-8"))):
            for pattern in PATTERNS:
                assert not re.search(pattern, text, re.IGNORECASE), (cid, pattern, text)
