"""Seam 1 of starting-notes (slice tester): the repository's real `cards/` and `notes/`."""

import re
from pathlib import Path

import yaml

from thinkhow.knowledge import read_notes

ROOT = Path(__file__).resolve().parents[3]
CARDS = ROOT / "cards"
NOTES = ROOT / "notes"
URL = re.compile(r"https?://\S+")
YEAR = re.compile(r"(?<!\d)(1[89]\d\d|20\d\d)(?!\d)")
CYRILLIC = re.compile(r"[А-Яа-яІіЇїЄєҐґ]")


def card_ids() -> list[str]:
    return sorted(yaml.safe_load(f.read_text(encoding="utf-8"))["id"] for f in CARDS.glob("*.yaml"))


def test_every_card_has_a_notes_file_with_exactly_its_router_and_facilitator_note() -> None:
    assert NOTES.is_dir(), "notes/ is missing"
    ids = card_ids()
    assert len(ids) == 25
    assert sorted(f.stem for f in NOTES.glob("*.yaml")) == ids
    records = read_notes(NOTES)
    assert len(records) == 50
    for cid in ids:
        raw = yaml.safe_load((NOTES / f"{cid}.yaml").read_text(encoding="utf-8"))
        assert isinstance(raw, list) and len(raw) == 2, cid
        by_id = {item["id"]: item for item in raw}
        assert sorted(by_id) == sorted([f"{cid}-router", f"{cid}-facilitator"]), cid
        assert by_id[f"{cid}-router"]["audience"] == "router", cid
        assert by_id[f"{cid}-facilitator"]["audience"] == "facilitator", cid
        assert cid in by_id[f"{cid}-router"]["cards"], cid
        assert by_id[f"{cid}-facilitator"]["cards"] == [cid], cid


def test_every_note_names_only_existing_cards() -> None:
    ids = set(card_ids())
    records = read_notes(NOTES)
    assert records
    for record in records:
        assert record.cards, record.id
        assert set(record.cards) <= ids, (record.id, record.cards)


def test_every_basis_is_non_empty_with_an_http_address_and_a_year() -> None:
    records = read_notes(NOTES)
    assert records
    for record in records:
        assert record.basis.strip(), record.id
        assert URL.search(record.basis), record.id
        assert YEAR.search(record.basis), record.id


def test_every_note_is_in_ukrainian() -> None:
    records = read_notes(NOTES)
    assert records
    for record in records:
        for name, text in (("title", record.title), ("noticed", record.noticed), ("do", record.do)):
            assert CYRILLIC.search(text), (record.id, name)
