"""Contract tests of skel-knowledge: store.current (slice tester; written from the contract, not the code)."""

from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from skelk_fakes import card_dict, put_json

from thinkhow.knowledge import Card, KnowledgeCorrupt, KnowledgeMissing, MemoryRecord, current
from thinkhow.platform.llm import KnowledgeRev
from thinkhow.platform.storage import LocalStorage


def memory_dict(mid: str, noticed: str = "помічено") -> dict[str, Any]:
    return {
        "id": mid,
        "title": f"запис {mid}",
        "cards": ["alpha"],
        "noticed": noticed,
        "do": "робити",
        "basis": "підстава",
    }


def change(rev: int, cards: dict[str, str], memory: dict[str, str] | None = None) -> dict[str, Any]:
    return {"rev": rev, "what": f"зміна {rev}", "why": "чому", "cards": cards, "memory": memory or {}}


def put_card(store: LocalStorage, cid: str, k: int, title: str) -> str:
    path = f"knowledge/cards/{cid}/v{k}.json"
    put_json(store, path, card_dict(cid, title=title))
    return path


def put_memory(store: LocalStorage, mid: str, k: int, noticed: str = "помічено") -> str:
    path = f"knowledge/memory/{mid}/v{k}.json"
    put_json(store, path, memory_dict(mid, noticed))
    return path


def put_change(
    store: LocalStorage,
    rev: int,
    cards: dict[str, str],
    memory: dict[str, str] | None = None,
    name_rev: int | None = None,
) -> None:
    put_json(
        store,
        f"knowledge/changes/{name_rev if name_rev is not None else rev:06d}.json",
        change(rev, cards, memory),
    )


def test_current_without_any_change_record_raises_knowledge_missing(tmp_path: Path) -> None:
    with pytest.raises(KnowledgeMissing):
        current(LocalStorage(tmp_path / "empty"))
    store = LocalStorage(tmp_path / "strangers")
    put_card(store, "alpha", 1, "Альфа")
    for stranger in (
        "knowledge/changes/notes.txt",
        "knowledge/changes/1.json",
        "knowledge/changes/old/000001.json",
        "knowledge/changes_old/000001.json",
    ):
        store.write("system", stranger, b"{}", "application/json")
    with pytest.raises(KnowledgeMissing):
        current(store)


def test_current_returns_the_versions_and_memory_of_the_record(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    a = put_card(store, "alpha", 1, "Альфа")
    m = put_memory(store, "M-001", 1)
    put_change(store, 1, {"alpha": a}, {"M-001": m})
    knowledge = current(store)
    assert knowledge.rev == 1
    assert knowledge.n == 0
    assert knowledge.cards == {"alpha": Card.model_validate(card_dict("alpha", title="Альфа"))}
    assert knowledge.memory == [MemoryRecord.model_validate(memory_dict("M-001"))]


def test_current_gives_memory_in_the_order_of_id(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    a = put_card(store, "alpha", 1, "Альфа")
    memory = {mid: put_memory(store, mid, 1) for mid in ("M-010", "M-001", "M-002")}
    put_change(store, 1, {"alpha": a}, memory)
    assert [record.id for record in current(store).memory] == ["M-001", "M-002", "M-010"]


def test_rev_pair_is_the_knowledge_rev_of_rev_and_n(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    a = put_card(store, "alpha", 1, "Альфа")
    put_change(store, 7, {"alpha": a})
    assert current(store).rev_pair() == KnowledgeRev(rev=7, n=0)


def test_current_refuses_a_record_whose_rev_is_not_its_file_name(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    a = put_card(store, "alpha", 1, "Альфа")
    put_change(store, 2, {"alpha": a}, name_rev=3)
    with pytest.raises(KnowledgeCorrupt):
        current(store)


def test_current_refuses_a_record_naming_a_missing_file(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path / "card")
    put_change(store, 1, {"alpha": "knowledge/cards/alpha/v1.json"})
    with pytest.raises(KnowledgeCorrupt):
        current(store)
    store = LocalStorage(tmp_path / "memory")
    a = put_card(store, "alpha", 1, "Альфа")
    put_change(store, 1, {"alpha": a}, {"M-001": "knowledge/memory/M-001/v1.json"})
    with pytest.raises(KnowledgeCorrupt):
        current(store)


def test_current_raises_validation_error_on_invalid_content(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path / "card")
    store.write("system", "knowledge/cards/alpha/v1.json", b'{"id": "alpha"}', "application/json")
    put_change(store, 1, {"alpha": "knowledge/cards/alpha/v1.json"})
    with pytest.raises(ValidationError):
        current(store)
    store = LocalStorage(tmp_path / "memory")
    a = put_card(store, "alpha", 1, "Альфа")
    store.write("system", "knowledge/memory/M-001/v1.json", b'{"id": "M-001"}', "application/json")
    put_change(store, 1, {"alpha": a}, {"M-001": "knowledge/memory/M-001/v1.json"})
    with pytest.raises(ValidationError):
        current(store)
    store = LocalStorage(tmp_path / "record")
    store.write("system", "knowledge/changes/000001.json", b'{"rev": 1}', "application/json")
    with pytest.raises(ValidationError):
        current(store)


def test_I2_current_returns_exactly_the_versions_named_by_the_largest_rev(tmp_path: Path) -> None:
    def alpha(title: str) -> Card:
        return Card.model_validate(card_dict("alpha", title=title))

    # Seam 3: records 1, 2, 10 and stranger files that sort after them as strings -> 10.
    store = LocalStorage(tmp_path / "seam3")
    a1, a2, a3 = (put_card(store, "alpha", k, f"Альфа {k}") for k in (1, 2, 3))
    b1 = put_card(store, "beta", 1, "Бета 1")
    m1 = put_memory(store, "M-001", 1)
    put_change(store, 1, {"alpha": a1, "beta": b1}, {"M-001": m1})
    put_change(store, 2, {"alpha": a2, "beta": b1}, {"M-001": m1})
    put_change(store, 10, {"alpha": a3})
    for stranger in (
        "knowledge/changes/zzz.json",
        "knowledge/changes/1000000.json",
        "knowledge/changes/999999.json.bak",
        "knowledge/changes/sub/000500.json",
        "knowledge/changes_old/000777.json",
    ):
        store.write("system", stranger, b"not a record", "application/json")
    knowledge = current(store)
    # nothing merged from records 1 and 2: beta and the memory record are gone in 10
    assert (knowledge.rev, knowledge.cards, knowledge.memory) == (10, {"alpha": alpha("Альфа 3")}, [])

    # numbers of different lengths: 9 and 10; 99 and 100; 99999 and 100000; up to 999999
    for revs in ((9, 10), (100, 99), (99999, 100000), (5, 999999, 123456)):
        store = LocalStorage(tmp_path / ("revs-" + "-".join(map(str, revs))))
        for rev in revs:
            put_change(
                store,
                rev,
                {"alpha": put_card(store, "alpha", rev, f"Альфа {rev}")},
                {"M-001": put_memory(store, "M-001", rev, f"помічено {rev}")},
            )
        top = max(revs)
        knowledge = current(store)
        assert knowledge.rev == top, revs
        assert knowledge.cards == {"alpha": alpha(f"Альфа {top}")}, revs
        assert knowledge.memory == [MemoryRecord.model_validate(memory_dict("M-001", f"помічено {top}"))], (
            revs
        )

    # the largest record names a card the smaller one does not, and a different memory
    store = LocalStorage(tmp_path / "grow")
    a1 = put_card(store, "alpha", 1, "Альфа 1")
    g1 = put_card(store, "gamma", 1, "Гамма 1")
    put_change(store, 1, {"alpha": a1}, {"M-001": put_memory(store, "M-001", 1)})
    put_change(store, 2, {"alpha": a1, "gamma": g1}, {"M-002": put_memory(store, "M-002", 1)})
    knowledge = current(store)
    assert knowledge.cards == {
        "alpha": alpha("Альфа 1"),
        "gamma": Card.model_validate(card_dict("gamma", title="Гамма 1")),
    }
    assert [record.id for record in knowledge.memory] == ["M-002"]
