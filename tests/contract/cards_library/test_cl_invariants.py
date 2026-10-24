"""Contract tests of cards-library: invariants I1-I5 of knowledge.publish. Slice tester; from the contract.

Inputs chosen by hand from each «Domain»: several revisions, stray version files of interrupted runs,
non-empty memory, ids `x` / `x-y`, added + changed + removed cards at once, a lawful publish after a
refused one, a storage that refuses halfway.
"""

import contextlib
from pathlib import Path

import yaml
from cl_fakes import (
    Boom,
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

from thinkhow.knowledge import Card, current, publish


def two_revisions(root: Path) -> RecordingStorage:
    """rev 1: alpha v1, beta v1, x v1, x-y v1; rev 2: beta v2, memory m1.

    Stray beta v3 and x v2 (no change record names them).
    """
    store = RecordingStorage(root)
    a1 = put_card(store, "alpha", 1, "Альфа")
    b1 = put_card(store, "beta", 1, "Бета")
    x1 = put_card(store, "x", 1, "Ікс")
    xy1 = put_card(store, "x-y", 1, "Ікс-ігрек")
    put_change(store, 1, {"alpha": a1, "beta": b1, "x": x1, "x-y": xy1})
    b2 = put_card(store, "beta", 2, "Бета-2")
    m1 = put_memory(store, "m1", 1, "alpha")
    put_change(store, 2, {"alpha": a1, "beta": b2, "x": x1, "x-y": xy1}, {"m1": m1})
    put_card(store, "beta", 3, "Бета з перерваного прогону")
    put_card(store, "x", 2, "Ікс з перерваного прогону")
    store.creates.clear()
    store.writes.clear()
    return store


def cards_of(cards: dict[str, str]) -> dict[str, Card]:
    return {cid: Card.model_validate(card_dict(cid, title)) for cid, title in cards.items()}


def unchanged_files(before: dict[str, bytes], after: dict[str, bytes]) -> None:
    for path, data in before.items():
        assert after.get(path) == data, path


def test_I1_publish_never_changes_or_removes_an_existing_file(tmp_path: Path) -> None:
    # a) lawful: alpha removed, beta changed, x changed (stray x v2), x-y kept, delta new
    root = tmp_path / "a"
    store = two_revisions(root)
    before = snapshot(root)
    folder = write_cards(
        tmp_path / "ca", {"beta": "Бета нова", "x": "Ікс новий", "x-y": "Ікс-ігрек", "delta": "Д"}
    )
    assert publish(store, folder) == 3
    unchanged_files(before, snapshot(root))
    assert store.writes == []
    # b) a second lawful publish on top of the first
    before = snapshot(root)
    folder2 = write_cards(tmp_path / "ca2", {"beta": "Бета ще нова", "x-y": "Ікс-ігрек"})
    assert publish(store, folder2) == 4
    unchanged_files(before, snapshot(root))
    # c) refused: an invalid card
    root = tmp_path / "c"
    store = two_revisions(root)
    before = snapshot(root)
    bad_folder = write_cards(tmp_path / "cc", {"alpha": "Альфа нова"})
    bad = card_dict("beta", "Бета нова")
    del bad["facilitator"]["phases"]
    write_card(bad_folder, bad)
    with contextlib.suppress(Exception):
        publish(store, bad_folder)
    unchanged_files(before, snapshot(root))
    # d) the storage refuses on the second create_if_absent
    root = tmp_path / "d"
    store = two_revisions(root)
    store.fail_on_create = 2
    before = snapshot(root)
    with contextlib.suppress(Boom):
        publish(store, write_cards(tmp_path / "cd", {"alpha": "А1", "beta": "Б1", "gamma": "Г1"}))
    unchanged_files(before, snapshot(root))
    assert store.writes == []


def test_I2_after_publish_returned_r_current_has_rev_r_and_exactly_the_folder_cards(tmp_path: Path) -> None:
    # a) added + changed + removed at once, on two revisions with stray files
    store = two_revisions(tmp_path / "a")
    wanted = {"beta": "Бета нова", "x": "Ікс новий", "x-y": "Ікс-ігрек", "delta": "Дельта"}
    r = publish(store, write_cards(tmp_path / "ca", wanted))
    assert r == 3
    now = current(store)
    assert now.rev == 3
    assert now.cards == cards_of(wanted)
    # b) a lawful publish after a refused one (file name other than the id)
    misnamed = write_cards(tmp_path / "cb", {"beta": "Бета"})
    write_card(misnamed, card_dict("x", "Ікс"), stem="wrong-name")
    with contextlib.suppress(ValueError):
        publish(store, misnamed)
    wanted = {"x": "Ікс"}  # x back to its v1 content, everything else removed
    r = publish(store, write_cards(tmp_path / "cb2", wanted))
    assert r == 4
    now = current(store)
    assert now.rev == 4
    assert now.cards == cards_of(wanted)


def test_I3_a_repeated_publish_with_the_same_folder_returns_none_and_writes_nothing(tmp_path: Path) -> None:
    # a) right after a publish that returned a number
    root = tmp_path / "a"
    store = two_revisions(root)
    folder = write_cards(tmp_path / "ca", {"alpha": "Альфа", "beta": "Бета нова", "delta": "Дельта"})
    assert publish(store, folder) == 3
    before = snapshot(root)
    assert publish(store, folder) is None
    assert snapshot(root) == before
    # b) right after a publish that returned None because the folder equals the current revision
    assert publish(store, folder) is None
    assert snapshot(root) == before
    # c) the same content, reformatted YAML, after a number
    reformatted = tmp_path / "ca-re"
    reformatted.mkdir()
    for cid, title in {"alpha": "Альфа", "beta": "Бета нова", "delta": "Дельта"}.items():
        text = yaml.safe_dump(card_dict(cid, title), allow_unicode=True, sort_keys=True, default_style='"')
        (reformatted / f"{cid}.yaml").write_text(text, encoding="utf-8")
    assert publish(store, reformatted) is None
    assert snapshot(root) == before
    # d) the folder equal to the current revision of two revisions (stray files present)
    root = tmp_path / "d"
    store = two_revisions(root)
    same = write_cards(tmp_path / "cd", {"alpha": "Альфа", "beta": "Бета-2", "x": "Ікс", "x-y": "Ікс-ігрек"})
    before = snapshot(root)
    assert publish(store, same) is None
    assert publish(store, same) is None
    assert snapshot(root) == before


def test_I4_an_unchanged_card_keeps_its_version_path_and_memory_keeps_its_paths(tmp_path: Path) -> None:
    store = two_revisions(tmp_path / "a")
    before = change_files(store)
    # beta unchanged at v2 (not v1, and its stray v3 ignored); x unchanged at v1 (stray v2 ignored);
    # x-y changed; alpha removed; delta new
    r = publish(
        store, write_cards(tmp_path / "ca", {"beta": "Бета-2", "x": "Ікс", "x-y": "Нове", "delta": "Д"})
    )
    assert r == 3
    record = new_change(store, before)
    assert record.cards["beta"] == "knowledge/cards/beta/v2.json"
    assert record.cards["x"] == "knowledge/cards/x/v1.json"
    assert record.memory == {"m1": "knowledge/memory/m1/v1.json"}
    # a second publish: the card changed in the first keeps the path the first gave it
    before = change_files(store)
    r = publish(
        store, write_cards(tmp_path / "cb", {"beta": "Бета-3", "x": "Ікс", "x-y": "Нове", "delta": "Д"})
    )
    assert r == 4
    second = new_change(store, before)
    assert second.cards["x-y"] == record.cards["x-y"]
    assert second.cards["delta"] == record.cards["delta"]
    assert second.cards["x"] == "knowledge/cards/x/v1.json"
    assert second.memory == {"m1": "knowledge/memory/m1/v1.json"}


def test_I5_when_publish_raises_current_gives_the_same_revision_as_before(tmp_path: Path) -> None:
    store = two_revisions(tmp_path / "a")
    expected = current(store)
    assert expected.rev == 2
    folders = []
    misnamed = write_cards(tmp_path / "f1", {"alpha": "Альфа нова"})
    write_card(misnamed, card_dict("beta", "Бета нова"), stem="gamma")
    folders.append(misnamed)
    empty = tmp_path / "f2"
    empty.mkdir()
    folders.append(empty)
    invalid = write_cards(tmp_path / "f3", {"alpha": "Альфа нова", "beta": "Бета нова"})
    bad = card_dict("zeta", "Зета")
    bad["id"] = "Zeta Upper"
    write_card(invalid, bad, stem="zeta")
    folders.append(invalid)
    broken = write_cards(tmp_path / "f4", {"alpha": "Альфа нова"})
    (broken / "beta.yaml").write_text("id: beta\ntitle: [\n", encoding="utf-8")
    folders.append(broken)
    for folder in folders:
        raised = False
        try:
            publish(store, folder)
        except (ValueError, yaml.YAMLError):  # pydantic.ValidationError is a ValueError
            raised = True
        assert raised, folder
        got = current(store)
        assert (got.rev, got.cards, got.memory) == (expected.rev, expected.cards, expected.memory), folder
    # the storage refuses halfway through the version files
    store.fail_on_create = 2
    raised = False
    try:
        publish(store, write_cards(tmp_path / "f5", {"alpha": "А1", "beta": "Б1", "gamma": "Г1", "x": "Ікс"}))
    except Boom:
        raised = True
    assert raised
    got = current(store)
    assert (got.rev, got.cards, got.memory) == (expected.rev, expected.cards, expected.memory)
