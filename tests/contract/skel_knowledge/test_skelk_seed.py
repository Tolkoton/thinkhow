"""Contract tests of skel-knowledge: store.seed (slice tester; written from the contract, not the code)."""

import contextlib
from collections.abc import Callable
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError
from skelk_fakes import Boom, RecordingStorage, card_dict, put_json, snapshot, write_card

from thinkhow.knowledge import Card, ChangeRecord, KnowledgeMissing, current, seed
from thinkhow.platform.storage import LocalStorage

CHANGE_1 = "knowledge/changes/000001.json"


def two_cards(tmp_path: Path) -> Path:
    cards_dir = tmp_path / "cards"
    write_card(cards_dir, card_dict("alpha", title="Альфа"))
    write_card(cards_dir, card_dict("beta", title="Бета"))
    return cards_dir


def expected_cards() -> dict[str, Card]:
    return {
        "alpha": Card.model_validate(card_dict("alpha", title="Альфа")),
        "beta": Card.model_validate(card_dict("beta", title="Бета")),
    }


def read_change(store: LocalStorage, path: str = CHANGE_1) -> ChangeRecord:
    data = store.read("system", path)
    assert data is not None, path
    return ChangeRecord.model_validate_json(data)


def test_first_seed_writes_version_files_and_change_record_1(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path / "bucket")
    assert seed(store, two_cards(tmp_path)) is True
    for cid, card in expected_cards().items():
        data = store.read("system", f"knowledge/cards/{cid}/v1.json")
        assert data is not None, cid
        assert Card.model_validate_json(data) == card
    assert read_change(store) == ChangeRecord(
        rev=1,
        what="посів: 2 стартових карток",
        why="ревізія 1 з теки cards/ репозиторію",
        cards={"alpha": "knowledge/cards/alpha/v1.json", "beta": "knowledge/cards/beta/v1.json"},
        memory={},
    )
    assert sorted(store.list("system", "")) == [
        "knowledge/cards/alpha/v1.json",
        "knowledge/cards/beta/v1.json",
        CHANGE_1,
    ]


def test_seed_writes_only_by_create_if_absent_into_system_as_json_change_record_last(tmp_path: Path) -> None:
    store = RecordingStorage(tmp_path / "bucket")
    assert seed(store, two_cards(tmp_path)) is True
    assert store.writes == []
    assert {(b, ct) for b, _, ct in store.creates} == {("system", "application/json")}
    paths = [p for _, p, _ in store.creates]
    assert paths[-1] == CHANGE_1
    assert sorted(paths[:-1]) == ["knowledge/cards/alpha/v1.json", "knowledge/cards/beta/v1.json"]


def test_seed_returns_the_result_of_the_last_create_if_absent(tmp_path: Path) -> None:
    # Another seeding run created the change record between this run's check and its creation.
    store = RecordingStorage(tmp_path / "bucket", forced={CHANGE_1: False})
    assert seed(store, two_cards(tmp_path)) is False
    assert [p for _, p, _ in store.creates][-1] == CHANGE_1


def test_seed_after_a_seed_returns_false_and_writes_nothing(tmp_path: Path) -> None:
    root = tmp_path / "bucket"
    cards_dir = two_cards(tmp_path)
    assert seed(LocalStorage(root), cards_dir) is True
    before = snapshot(root)
    assert seed(LocalStorage(root), cards_dir) is False
    assert snapshot(root) == before


def test_seed_that_failed_halfway_leaves_no_revision_and_a_repeat_completes_it(tmp_path: Path) -> None:
    cards_dir = two_cards(tmp_path)
    # Two cards: three create_if_absent calls (two v1.json, then the change record). Fail on each in turn.
    for n in (1, 2, 3):
        root = tmp_path / f"bucket-{n}"
        with contextlib.suppress(Boom):
            seed(RecordingStorage(root, fail_on_create=n), cards_dir)
        with pytest.raises(KnowledgeMissing):
            current(LocalStorage(root))
        assert seed(LocalStorage(root), cards_dir) is True, n
        knowledge = current(LocalStorage(root))
        assert (knowledge.rev, knowledge.n, knowledge.memory) == (1, 0, []), n
        assert knowledge.cards == expected_cards(), n


def test_seed_with_only_stranger_files_under_changes_seeds(tmp_path: Path) -> None:
    root = tmp_path / "bucket"
    store = LocalStorage(root)
    for stranger in (
        "knowledge/changes/notes.txt",
        "knowledge/changes/1.json",
        "knowledge/changes/0000001.json",
        "knowledge/changes/000001.json.bak",
        "knowledge/changes/old/000005.json",
        "knowledge/changes_old/000007.json",
    ):
        store.write("system", stranger, b"{}", "application/json")
    assert seed(store, two_cards(tmp_path)) is True
    assert read_change(store).rev == 1
    assert current(store).rev == 1


def test_seed_reads_only_yaml_files_of_cards_dir(tmp_path: Path) -> None:
    cards_dir = tmp_path / "cards"
    write_card(cards_dir, card_dict("alpha", title="Альфа"))
    (cards_dir / "README.md").write_text("не картка: [зламаний yaml", encoding="utf-8")
    (cards_dir / "beta.yml").write_text("id: [зламаний", encoding="utf-8")
    store = LocalStorage(tmp_path / "bucket")
    assert seed(store, cards_dir) is True
    assert read_change(store).cards == {"alpha": "knowledge/cards/alpha/v1.json"}
    assert read_change(store).what == "посів: 1 стартових карток"


def test_seed_refuses_a_file_name_that_is_not_the_card_id(tmp_path: Path) -> None:
    cards_dir = tmp_path / "cards"
    write_card(cards_dir, card_dict("alpha"), stem="not-alpha")
    with pytest.raises(ValueError):
        seed(LocalStorage(tmp_path / "bucket"), cards_dir)


def test_seed_refuses_an_empty_cards_dir(tmp_path: Path) -> None:
    cards_dir = tmp_path / "cards"
    cards_dir.mkdir()
    with pytest.raises(ValueError):
        seed(LocalStorage(tmp_path / "bucket"), cards_dir)


def test_seed_raises_validation_error_on_an_invalid_card(tmp_path: Path) -> None:
    cards_dir = tmp_path / "cards"
    bad = card_dict("alpha")
    bad["facilitator"]["phases"] = []
    write_card(cards_dir, bad)
    with pytest.raises(ValidationError):
        seed(LocalStorage(tmp_path / "bucket"), cards_dir)


def test_seed_raises_yaml_error_on_malformed_yaml(tmp_path: Path) -> None:
    cards_dir = tmp_path / "cards"
    cards_dir.mkdir()
    (cards_dir / "alpha.yaml").write_text("id: alpha\nrouter: [unclosed\n", encoding="utf-8")
    with pytest.raises(yaml.YAMLError):
        seed(LocalStorage(tmp_path / "bucket"), cards_dir)


def test_I1_seed_never_changes_knowledge_that_has_a_change_record(tmp_path: Path) -> None:
    good_dir = two_cards(tmp_path)
    # a cards_dir with one changed card and one added card
    changed_dir = tmp_path / "cards-changed"
    write_card(changed_dir, card_dict("alpha", title="Альфа ЗМІНЕНА"))
    write_card(changed_dir, card_dict("beta", title="Бета"))
    write_card(changed_dir, card_dict("gamma", title="Гамма"))
    empty_dir = tmp_path / "cards-empty"
    empty_dir.mkdir()
    broken_dir = tmp_path / "cards-broken"
    broken_dir.mkdir()
    (broken_dir / "alpha.yaml").write_text("id: [зламаний\n", encoding="utf-8")
    misnamed_dir = tmp_path / "cards-misnamed"
    write_card(misnamed_dir, card_dict("alpha"), stem="omega")
    dirs = [good_dir, changed_dir, empty_dir, broken_dir, misnamed_dir]

    def seeded(root: Path) -> None:
        assert seed(LocalStorage(root), good_dir) is True

    def only_record(name: str, content: bytes) -> Callable[[Path], None]:
        def make(root: Path) -> None:
            LocalStorage(root).write("system", f"knowledge/changes/{name}", content, "application/json")

        return make

    def half_seeded_plus_record_2(root: Path) -> None:
        # a v1.json of a failed seeding run, and a later revision written by learning
        store = LocalStorage(root)
        put_json(store, "knowledge/cards/alpha/v1.json", card_dict("alpha", title="Альфа"))
        put_json(
            store,
            "knowledge/changes/000002.json",
            {
                "rev": 2,
                "what": "w",
                "why": "y",
                "cards": {"alpha": "knowledge/cards/alpha/v1.json"},
                "memory": {},
            },
        )

    states = {
        "after a seed": seeded,
        "only 000002.json": only_record("000002.json", b'{"rev": 2}'),
        "only 000000.json": only_record("000000.json", b"{}"),
        "only 999999.json": only_record("999999.json", b"{}"),
        "only an unreadable 000001.json": only_record("000001.json", b"not json at all"),
        "a v1.json and 000002.json": half_seeded_plus_record_2,
    }
    for state, make in states.items():
        for cards_dir in dirs:
            root = tmp_path / "buckets" / state.replace(" ", "_") / cards_dir.name
            make(root)
            before = snapshot(root)
            assert seed(LocalStorage(root), cards_dir) is False, (state, cards_dir.name)
            # a repeat after the refusal is refused the same way
            assert seed(LocalStorage(root), cards_dir) is False, (state, cards_dir.name)
            assert snapshot(root) == before, (state, cards_dir.name)
