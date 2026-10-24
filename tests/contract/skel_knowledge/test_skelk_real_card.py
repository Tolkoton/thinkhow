"""Contract tests of skel-knowledge: the real card `cards/pre-mortem.yaml` (Seam 2) and seeding
the repository's `cards/` (exit criterion). Slice tester; written from the contract, not the code."""

from pathlib import Path

import yaml

from thinkhow.knowledge import Card, card_prompt, current, seed
from thinkhow.platform.storage import LocalStorage

REPO = Path(__file__).resolve().parents[3]
CARDS_DIR = REPO / "cards"
POC_PHASES = [
    "phase_1_time_travel",
    "phase_2_blind_spots",
    "phase_3_triage",
    "phase_4_mitigation_tripwires",
]
# The repository's `cards/` after task 302: exactly the 18 ids of cards-library «Goal» 1 (sorted by hand).
REPOSITORY_CARD_IDS = [
    "complexity-sensemaking",
    "consider-opposite",
    "evaporating-cloud",
    "first-principles",
    "five-whys",
    "goal-to-plan",
    "is-is-not",
    "issue-tree",
    "jobs-to-be-done",
    "mental-contrasting",
    "opportunity-tree",
    "pre-mortem",
    "reflective-cycle",
    "reversible-doors",
    "scamper",
    "socratic-questioning",
    "weighted-matrix",
    "wrap-decision",
]


def load_real_card() -> Card:
    return Card.model_validate(yaml.safe_load((CARDS_DIR / "pre-mortem.yaml").read_text(encoding="utf-8")))


def test_real_card_is_valid_with_the_four_poc_phases_in_order() -> None:
    card = load_real_card()
    assert card.id == "pre-mortem"
    assert [phase.id for phase in card.facilitator.phases] == POC_PHASES
    assert all(phase.exit.strip() for phase in card.facilitator.phases)


def test_real_card_keeps_lines_without_a_field_as_how_items() -> None:
    phases = {phase.id: phase for phase in load_real_card().facilitator.phases}
    assert any("доконаному минулому" in item for item in phases["phase_1_time_travel"].how)
    assert any(
        "Ця фаза не пропускається ніколи" in item for item in phases["phase_4_mitigation_tripwires"].how
    )


def test_real_card_prompt_has_every_phase_id_and_exit() -> None:
    card = load_real_card()
    text = card_prompt(card)
    for phase in card.facilitator.phases:
        assert phase.id in text
        assert phase.exit in text


def test_seeding_the_repository_cards_gives_revision_1_with_pre_mortem(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    assert seed(store, CARDS_DIR) is True
    assert seed(store, CARDS_DIR) is False
    knowledge = current(store)
    assert (knowledge.rev, knowledge.n, sorted(knowledge.cards), knowledge.memory) == (
        1,
        0,
        REPOSITORY_CARD_IDS,
        [],
    )
    assert knowledge.cards["pre-mortem"] == load_real_card()
