"""Contract tests of product-cards: invariants I1-I5. Slice tester; from the contract, not the code.

The «Domain» of I1-I4 is every card of the real `cards/` (25 after the slice), so each test runs over every
file there and first requires the 25 ids of the goal; I5 runs over every case id of commit 6091f88.
"""

import re
from collections import Counter

from pc_helpers import CASES, ROOT, all_card_ids, cases, load, normalise, old_cases, strings

from thinkhow.knowledge import Card

RESEARCH = (ROOT / "docs/research/01-library.md").read_text(encoding="utf-8") + (
    ROOT / "docs/research/04-product-pack.md"
).read_text(encoding="utf-8")
BANNED = [
    *(re.escape(m) for m in ("Kepner", "Cynefin", "WOOP", "GROW™", "Outcome-Driven", "Six Thinking Hats")),
    r"\bODI\b",
    r"\bSPIN\b",
    re.escape("Blue Ocean"),
    re.escape("Value Proposition Canvas"),
    # the bans of task 302 (cards-library Seam 5): «час змінити метод» and crisis text
    r"час змінити метод",
    r"кризов",
    r"гаряч\w* лін",
    r"\b0800\b|\b11[26]\b|\+\d{6,}",
]
SAME_FIELDS = ("kind", "text", "expect", "not_first", "history", "offered", "absent", "ended")


def method_names(method: str) -> list[str]:
    head = method.split("(")[0]
    return [part.strip() for part in re.split(r",| і ", head)]


def test_I1_every_card_valid_named_by_its_file_ends_ne_toi_vypadok_names_a_researched_method() -> None:
    assert "Invented Thing" not in method_names("Pretotyping і гіпотеза XYZ (Savoia)")
    assert method_names("Pretotyping і гіпотеза XYZ (Savoia)") == ["Pretotyping", "гіпотеза XYZ"]
    for cid in all_card_ids():
        card = Card.model_validate(load(cid))
        assert card.id == cid
        assert card.facilitator.traps, cid
        assert card.facilitator.traps[-1].name == "Не той випадок", cid
        if cid == "pre-mortem":
            continue
        assert card.method.strip(), cid
        for name in method_names(card.method):
            assert name and name in RESEARCH, (cid, name)


def test_I2_every_card_has_three_positives_exactly_one_held_out_and_a_negative_with_it_in_not_first() -> None:
    all_cases = cases()
    positives = Counter(c["expect"] for c in all_cases if c["kind"] == "positive")
    held = Counter(c["expect"] for c in all_cases if c["kind"] == "positive" and c["id"].endswith("-3"))
    for cid in all_card_ids():
        assert positives[cid] >= 3, (cid, positives[cid])
        assert held[cid] == 1, (cid, held[cid])
        assert any(c["kind"] == "negative" and cid in c.get("not_first", []) for c in all_cases), cid


def _six_grams(text: str) -> set[tuple[str, ...]]:
    words = re.findall(r"[\w']+", normalise()(text))
    return {tuple(words[i : i + 6]) for i in range(len(words) - 5)}


def test_I3_no_six_words_in_a_row_of_any_case_stand_in_one_router_item_of_any_card() -> None:
    grams: set[tuple[str, ...]] = set()
    for case in cases():
        grams |= _six_grams(case["text"])
    assert grams
    for cid in all_card_ids():
        router = load(cid)["router"]
        for item in [router["needs"], *router["when_yes"], *router["when_no"], *router["signals"]]:
            hit = _six_grams(item) & grams
            assert not hit, (cid, item, hit)


def test_I4_no_trademark_no_change_method_phrase_no_crisis_text_in_any_card_but_pre_mortem() -> None:
    assert re.search(BANNED[7], "Метод spin продажів", re.IGNORECASE)  # the rule is case-insensitive
    for cid in all_card_ids():
        if cid == "pre-mortem":
            continue
        for text in strings(load(cid)):
            for pattern in BANNED:
                assert not re.search(pattern, text, re.IGNORECASE), (cid, pattern, text)


def _region(raw: list[str], case_id: str) -> list[str]:
    start = raw.index(f"  - id: {case_id}")
    end = next((i for i in range(start + 1, len(raw)) if raw[i].startswith("  - id: ")), len(raw))
    return raw[start:end]


def _marked(region: list[str], entry: str) -> bool:
    """The added entry stands in a line with `# 307:` (or right under a `# 307:` comment line)."""
    token = re.compile(rf"(?<![\w-]){re.escape(entry)}(?![\w-])")
    for i, line in enumerate(region):
        if not token.search(line.split("#")[0]):
            continue
        if re.search(r"#\s*307:", line):
            return True
        if i > 0 and re.match(r"\s*#\s*307:", region[i - 1]):
            return True
    return False


def test_I5_the_85_old_cases_keep_their_fields_and_also_ok_is_only_added_to_with_a_307_comment() -> None:
    raw = CASES.read_text(encoding="utf-8").splitlines()
    old = old_cases()
    assert len(old) == 85
    now = {c["id"]: c for c in cases()}
    for before in old:
        cid = before["id"]
        assert cid in now, cid
        after = now[cid]
        for field in SAME_FIELDS:
            assert after.get(field) == before.get(field), (cid, field)
        old_ok = list(before.get("also_ok", []))
        new_ok = list(after.get("also_ok", []))
        assert set(old_ok) <= set(new_ok), (cid, old_ok, new_ok)
        for entry in (e for e in new_ok if e not in old_ok):
            assert _marked(_region(raw, cid), entry), (cid, entry)
