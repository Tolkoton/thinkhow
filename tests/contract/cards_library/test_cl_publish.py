"""Contract tests of cards-library: knowledge.publish (Seam 1-3, errors).
Slice tester; written from the contract, not the code."""

from pathlib import Path

import pytest
import yaml
from cl_fakes import (
    CHANGES,
    WHY,
    RecordingStorage,
    card_dict,
    change_files,
    new_change,
    put_card,
    put_change,
    put_memory,
    snapshot,
    write_card,
    write_cards,
)
from pydantic import ValidationError

from thinkhow.knowledge import Card, KnowledgeCorrupt, KnowledgeMissing, current, publish
from thinkhow.platform.storage import LocalStorage

ALPHA = "knowledge/cards/alpha/v1.json"
BETA = "knowledge/cards/beta/v1.json"


def seeded_two(root: Path) -> RecordingStorage:
    """Revision 1 by hand: alpha «Альфа», beta «Бета», one memory record."""
    store = RecordingStorage(root)
    put_card(store, "alpha", 1, "Альфа")
    put_card(store, "beta", 1, "Бета")
    put_change(store, 1, {"alpha": ALPHA, "beta": BETA}, {"m1": put_memory(store, "m1", 1, "alpha")})
    return store


def test_seam1_changed_title_gets_v2_the_other_card_keeps_v1_and_memory_is_kept(tmp_path: Path) -> None:
    store = seeded_two(tmp_path / "bucket")
    cards_dir = write_cards(tmp_path / "cards", {"alpha": "Альфа", "beta": "Бета нова"})
    before = change_files(store)
    assert publish(store, cards_dir) == 2
    record = new_change(store, before)
    assert record.rev == 2
    assert record.cards == {"alpha": ALPHA, "beta": "knowledge/cards/beta/v2.json"}
    assert record.memory == {"m1": "knowledge/memory/m1/v1.json"}
    assert record.why == WHY
    data = store.read("system", "knowledge/cards/beta/v2.json")
    assert data is not None
    assert Card.model_validate_json(data) == Card.model_validate(card_dict("beta", "Бета нова"))
    assert sorted(store.list("system", "knowledge/cards/alpha/")) == [ALPHA]


def test_seam1_same_folder_returns_none_and_the_storage_is_unchanged(tmp_path: Path) -> None:
    root = tmp_path / "bucket"
    store = seeded_two(root)
    cards_dir = write_cards(tmp_path / "cards", {"alpha": "Альфа", "beta": "Бета"})
    before = snapshot(root)
    assert publish(store, cards_dir) is None
    assert snapshot(root) == before


def test_seam1_reformatted_yaml_with_the_same_content_returns_none(tmp_path: Path) -> None:
    root = tmp_path / "bucket"
    store = seeded_two(root)
    cards_dir = tmp_path / "cards"
    cards_dir.mkdir()
    for cid, title in {"alpha": "Альфа", "beta": "Бета"}.items():
        # other key order, every scalar double-quoted, other indentation: the same Card
        text = yaml.safe_dump(
            card_dict(cid, title), allow_unicode=True, sort_keys=True, default_style='"', indent=4
        )
        (cards_dir / f"{cid}.yaml").write_text(text, encoding="utf-8")
    assert Card.model_validate(yaml.safe_load((cards_dir / "alpha.yaml").read_text(encoding="utf-8"))) == (
        Card.model_validate(card_dict("alpha", "Альфа"))
    )
    before = snapshot(root)
    assert publish(store, cards_dir) is None
    assert snapshot(root) == before


def test_seam2_only_create_if_absent_into_system_as_json_versions_first_change_record_last(
    tmp_path: Path,
) -> None:
    store = seeded_two(tmp_path / "bucket")
    store.creates.clear()
    store.writes.clear()
    cards_dir = write_cards(
        tmp_path / "cards", {"alpha": "Альфа нова", "beta": "Бета нова", "gamma": "Гамма"}
    )
    assert publish(store, cards_dir) == 2
    assert store.writes == []
    assert {(b, ct) for b, _, ct in store.creates} == {("system", "application/json")}
    paths = [p for _, p, _ in store.creates]
    assert paths[-1].startswith(CHANGES)
    assert sorted(paths[:-1]) == [
        "knowledge/cards/alpha/v2.json",
        "knowledge/cards/beta/v2.json",
        "knowledge/cards/gamma/v1.json",
    ]


def test_seam2_change_record_already_created_by_another_run_returns_none(tmp_path: Path) -> None:
    store = seeded_two(tmp_path / "bucket")
    store.forced_prefix = (CHANGES, False)
    cards_dir = write_cards(tmp_path / "cards", {"alpha": "Альфа", "beta": "Бета нова"})
    assert publish(store, cards_dir) is None
    assert [p for _, p, _ in store.creates][-1].startswith(CHANGES)


def test_seam2_version_file_already_created_by_another_run_returns_none_without_a_change_record(
    tmp_path: Path,
) -> None:
    store = seeded_two(tmp_path / "bucket")
    store.forced = {"knowledge/cards/beta/v2.json": False}
    cards_dir = write_cards(tmp_path / "cards", {"alpha": "Альфа", "beta": "Бета нова"})
    before = change_files(store)
    assert publish(store, cards_dir) is None
    assert change_files(store) == before
    assert not any(p.startswith(CHANGES) for _, p, _ in store.creates)
    assert current(store).rev == 1


def test_seam3_changed_card_with_a_stray_v2_gets_v3_and_v2_is_never_attempted(tmp_path: Path) -> None:
    store = seeded_two(tmp_path / "bucket")
    put_card(store, "beta", 2, "Бета з перерваного прогону")  # no change record names it
    store.creates.clear()
    cards_dir = write_cards(tmp_path / "cards", {"alpha": "Альфа", "beta": "Бета нова"})
    before = change_files(store)
    assert publish(store, cards_dir) == 2
    assert new_change(store, before).cards["beta"] == "knowledge/cards/beta/v3.json"
    assert "knowledge/cards/beta/v2.json" not in [p for _, p, _ in store.creates]


def test_seam3_unchanged_card_keeps_v1_while_its_stray_v2_lies_in_the_storage(tmp_path: Path) -> None:
    store = seeded_two(tmp_path / "bucket")
    put_card(store, "alpha", 2, "Альфа з перерваного прогону")
    cards_dir = write_cards(tmp_path / "cards", {"alpha": "Альфа", "beta": "Бета нова"})
    before = change_files(store)
    assert publish(store, cards_dir) == 2
    assert new_change(store, before).cards["alpha"] == ALPHA


def test_seam3_files_of_x_y_do_not_count_for_the_version_of_x(tmp_path: Path) -> None:
    store = RecordingStorage(tmp_path / "bucket")
    x1 = put_card(store, "x", 1, "Ікс")
    for k in (1, 2, 3, 4):
        xy = put_card(store, "x-y", k, f"Ікс-ігрек {k}")
    put_change(store, 1, {"x": x1, "x-y": xy})
    cards_dir = write_cards(tmp_path / "cards", {"x": "Ікс новий", "x-y": "Ікс-ігрек 4"})
    before = change_files(store)
    assert publish(store, cards_dir) == 2
    assert new_change(store, before).cards == {"x": "knowledge/cards/x/v2.json", "x-y": xy}


def test_seam3_content_equal_to_an_older_version_but_not_the_current_one_gets_a_new_version(
    tmp_path: Path,
) -> None:
    store = RecordingStorage(tmp_path / "bucket")
    a1 = put_card(store, "alpha", 1, "Альфа")
    b1 = put_card(store, "beta", 1, "Бета")
    put_change(store, 1, {"alpha": a1, "beta": b1})
    b2 = put_card(store, "beta", 2, "Бета-2")
    put_change(store, 2, {"alpha": a1, "beta": b2})
    cards_dir = write_cards(
        tmp_path / "cards", {"alpha": "Альфа", "beta": "Бета"}
    )  # beta back to v1's content
    before = change_files(store)
    assert publish(store, cards_dir) == 3
    assert new_change(store, before).cards == {"alpha": a1, "beta": "knowledge/cards/beta/v3.json"}


def test_seam3_what_names_new_changed_and_removed_ids(tmp_path: Path) -> None:
    store = RecordingStorage(tmp_path / "bucket")
    paths = {cid: put_card(store, cid, 1, cid.upper()) for cid in ("alpha", "beta", "gamma")}
    put_change(store, 1, paths)
    # alpha unchanged, beta changed, gamma removed, delta new
    cards_dir = write_cards(tmp_path / "cards", {"alpha": "ALPHA", "beta": "BETA нова", "delta": "DELTA"})
    before = change_files(store)
    assert publish(store, cards_dir) == 2
    what = new_change(store, before).what
    for cid in ("beta", "gamma", "delta"):
        assert cid in what, (cid, what)


def test_publish_on_unseeded_knowledge_raises_knowledge_missing(tmp_path: Path) -> None:
    root = tmp_path / "bucket"
    store = LocalStorage(root)
    put_card(store, "alpha", 1, "Альфа")  # a version file but no change record
    cards_dir = write_cards(tmp_path / "cards", {"alpha": "Альфа нова"})
    with pytest.raises(KnowledgeMissing):
        publish(store, cards_dir)


def test_publish_raises_knowledge_corrupt_when_the_change_record_names_a_missing_file(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path / "bucket")
    a1 = put_card(store, "alpha", 1, "Альфа")
    put_change(store, 1, {"alpha": a1, "beta": "knowledge/cards/beta/v1.json"})
    cards_dir = write_cards(tmp_path / "cards", {"alpha": "Альфа нова"})
    with pytest.raises(KnowledgeCorrupt):
        publish(store, cards_dir)


def test_publish_raises_value_error_on_an_empty_folder_or_a_file_name_other_than_the_id(
    tmp_path: Path,
) -> None:
    store = seeded_two(tmp_path / "bucket")
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(ValueError):
        publish(store, empty)
    misnamed = write_cards(tmp_path / "misnamed", {"alpha": "Альфа"})
    write_card(misnamed, card_dict("beta", "Бета нова"), stem="not-beta")
    with pytest.raises(ValueError):
        publish(store, misnamed)


def test_publish_raises_validation_error_on_an_invalid_card(tmp_path: Path) -> None:
    store = seeded_two(tmp_path / "bucket")
    cards_dir = write_cards(tmp_path / "cards", {"alpha": "Альфа"})
    bad = card_dict("beta", "Бета нова")
    bad["router"]["when_yes"] = []  # the schema demands at least one
    write_card(cards_dir, bad)
    with pytest.raises(ValidationError):
        publish(store, cards_dir)


def test_publish_raises_yaml_error_on_broken_yaml(tmp_path: Path) -> None:
    store = seeded_two(tmp_path / "bucket")
    cards_dir = write_cards(tmp_path / "cards", {"alpha": "Альфа"})
    (cards_dir / "beta.yaml").write_text("id: beta\ntitle: [не закрито\n  router: {\n", encoding="utf-8")
    with pytest.raises(yaml.YAMLError):
        publish(store, cards_dir)
