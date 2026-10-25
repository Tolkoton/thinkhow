"""Task 205: the router names each method it offers; the facilitator names the chosen one and explains it.

The owner's words (2026-10-25) replace task 301's «людина не мусить знати «Pre-mortem»» and task 302's «назв
методів людині роутер не каже». Names come from the cards, the cards' names from research 01 §7(ґ).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

import yaml

from thinkhow.facilitation.respond import ROUTED_SECTION, RULES, _state
from thinkhow.facilitation.route import ROUTER_RULES, router_instruction
from thinkhow.facilitation.types import Decision, FacilitationContext, ProblemMap, Rev
from thinkhow.knowledge import Card, CurrentKnowledge, card_prompt, current, publish, seed
from thinkhow.platform.storage import LocalStorage

ROOT = Path(__file__).resolve().parents[3]
CARDS = ROOT / "cards"
RESEARCH_01 = (ROOT / "docs/research/01-library.md").read_text(encoding="utf-8")
RESEARCH_04 = (ROOT / "docs/research/04-product-pack.md").read_text(encoding="utf-8")
JUST_CHOSEN = "[Стан] Метод щойно обрано"


def card(cid: str, method: str | None = None) -> Card:
    data = {
        "id": cid,
        "title": f"Заголовок {cid}",
        "router": {"needs": "н", "when_yes": ["так"], "when_no": ["ні"], "signals": ["с"]},
        "facilitator": {
            "purpose": "навіщо",
            "stance": "позиція",
            "needs": "на вході",
            "phases": [{"id": "x_one", "title": "Ф", "goal": "мета", "how": ["як"], "exit": "вихід"}],
            "ending": "кінець",
            "traps": [],
            "pairs_well": "поєднується",
        },
    }
    return Card.model_validate(data if method is None else data | {"method": method})


ALPHA = card("alpha")


def _named(cid: str, method: str) -> Card:
    return card(cid, method)


def _real_cards() -> list[Card]:
    return [Card.model_validate(yaml.safe_load(f.read_text("utf-8"))) for f in sorted(CARDS.glob("*.yaml"))]


# --- the cards carry the method's name ---


def test_a_card_without_a_method_still_loads_so_stored_revisions_stay_readable() -> None:
    assert ALPHA.method == ""


def test_every_card_names_its_method_pre_mortem_by_its_sealed_title() -> None:
    """pre-mortem.yaml stays byte for byte (blob 8f52b66a, task 302): its title starts with the name."""
    cards = {c.id: c for c in _real_cards()}
    assert len(cards) == len(list(CARDS.glob("*.yaml")))
    pre_mortem = cards.pop("pre-mortem")
    assert pre_mortem.method == "" and pre_mortem.title.startswith("Pre-mortem")
    assert [c.id for c in cards.values() if not c.method.strip()] == []


def test_every_method_name_stands_in_research_01_or_04_not_invented() -> None:
    """Each name the card gives — the part before any bracket, split on «,» and «і» — is in research 01
    or, for the product cards of task 307, in research 04."""
    for c in _real_cards():
        head = c.method.split("(")[0]
        for name in (part.strip() for part in re.split(r",| і ", head) if c.method):
            assert name and (name in RESEARCH_01 or name in RESEARCH_04), (c.id, name)


def test_names_research_01_s3_6_marks_as_trademarks_stay_out_task_302_ban_holds() -> None:
    """«Is / Is-Not», not Kepner-Tregoe®; «Complexity Sensemaking», not Cynefin®; «MCII», not WOOP; and the
    marks of research 04 §5 (task 307): SPIN®, Blue Ocean, Strategyzer's Value Proposition Canvas."""
    for c in _real_cards():
        for mark in ("Kepner", "Cynefin", "WOOP", "GROW™", "SPIN", "Blue Ocean", "Value Proposition Canvas"):
            assert mark.lower() not in c.method.lower(), (c.id, mark)


# --- the router sees the name and must say it ---


def _knowledge(*cards: Card) -> CurrentKnowledge:
    return CurrentKnowledge(rev=3, n=1, cards={c.id: c for c in cards}, memory=[])


def test_the_router_reads_the_method_of_every_card() -> None:
    text = router_instruction(_knowledge(_named("alpha", "Pre-mortem"), _named("beta", "WRAP")), "uk")
    assert "### alpha — Заголовок alpha\nМетод: Pre-mortem\n" in text
    assert "### beta — Заголовок beta\nМетод: WRAP\n" in text


def test_a_card_without_a_method_gives_the_router_no_empty_line() -> None:
    assert "Метод:" not in router_instruction(_knowledge(ALPHA), "uk").split("# Картка за карткою")[1]


def test_the_router_rules_ask_to_name_each_method_and_no_longer_forbid_it() -> None:
    assert "ніколи не називай методів" not in ROUTER_RULES
    assert "називай назвою його методу" in ROUTER_RULES
    assert "простими словами" in ROUTER_RULES


# --- the facilitator names it and explains how it leads ---


def test_the_facilitator_card_text_carries_the_method() -> None:
    assert "# Картка: Заголовок alpha\n\n**Метод.** Pre-mortem\n\n" in card_prompt(
        _named("alpha", "Pre-mortem")
    )


def test_a_card_without_a_method_has_no_method_line_for_the_facilitator() -> None:
    assert "**Метод.**" not in card_prompt(ALPHA)


def test_the_facilitator_rules_ask_to_name_explain_and_walk_the_phases() -> None:
    assert "не називай їх у reply" not in RULES
    for words in (
        "звідки він",
        "з яких фаз",
        "навіщо він саме тут",
        "що ми зараз робимо і чому",
        JUST_CHOSEN,
    ):
        assert words in RULES, words
    assert "не називай методів" not in ROUTED_SECTION


def _decision(turn: int, kind: Literal["choose", "end"], card_id: str | None) -> Decision:
    return Decision(
        turn=turn,
        rev=Rev(rev=3, n=1),
        kind=kind,
        profile=None,
        candidates=[],
        card_id=card_id,
        end="done" if kind == "end" else None,
        why="w",
    )


def _ctx(turn: int, routing: tuple[Decision, ...] | None) -> FacilitationContext:
    return FacilitationContext(
        card_id="alpha", history=[], problem_map=ProblemMap(), turn_no=turn, text="т", routing=routing
    )


def test_the_turn_a_card_is_chosen_tells_the_facilitator_to_explain_the_method() -> None:
    assert _state(_ctx(5, (_decision(5, "choose", "alpha"),))).startswith(JUST_CHOSEN)


def test_a_new_card_after_another_is_explained_the_same_way() -> None:
    routing = (_decision(2, "choose", "beta"), _decision(7, "end", "beta"), _decision(9, "choose", "alpha"))
    assert _state(_ctx(9, routing)).startswith(JUST_CHOSEN)


def test_the_turns_after_the_choice_carry_no_such_line() -> None:
    assert JUST_CHOSEN not in _state(_ctx(6, (_decision(5, "choose", "alpha"),)))
    assert JUST_CHOSEN not in _state(_ctx(1, None))


# --- the prototype gets the names: the Job `cards` publishes the changed cards ---


def test_publish_gives_a_card_stored_without_a_method_a_new_version_with_it(tmp_path: Path) -> None:
    """Revision 2 on the prototype has no `method`; the same card with it is a changed card → v2, rev + 1."""
    storage = LocalStorage(tmp_path / "store")
    old, new = tmp_path / "old", tmp_path / "new"
    old.mkdir()
    new.mkdir()
    for folder, method in ((old, None), (new, "WRAP")):
        data = card("alpha", method).model_dump(exclude_unset=True)
        (folder / "alpha.yaml").write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    assert seed(storage, old)
    assert publish(storage, new) == 2
    assert current(storage).cards["alpha"].method == "WRAP"
    assert publish(storage, new) is None
