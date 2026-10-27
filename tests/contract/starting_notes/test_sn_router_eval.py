"""`scripts/router_eval.py --notes <dir>` (slice tester; from the contract, not the code).

The routing itself is replaced by a recorder of the Knowledge it is given (`run` takes the Knowledge as a
parameter); the model port is a double that fails on any call, so a vet through the model would show.
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import yaml
from sn_fakes import as_record, facilitator, router, write_file

from thinkhow.knowledge import CurrentKnowledge
from thinkhow.platform import llm as pl

ROOT = Path(__file__).resolve().parents[3]


def load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("sn_router_eval", ROOT / "scripts" / "router_eval.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class NoModel:
    calls = 0

    def _fail(self, *args: Any, **kwargs: Any) -> Any:
        NoModel.calls += 1
        raise AssertionError("no model call is expected in this run")

    generate_json = stream_json = search_text = _fail


def two_card_ids() -> list[str]:
    return sorted(
        yaml.safe_load(f.read_text(encoding="utf-8"))["id"] for f in (ROOT / "cards").glob("*.yaml")
    )[:2]


def main_with(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, extra: list[str]) -> list[CurrentKnowledge]:
    module = load()
    seen: list[CurrentKnowledge] = []

    def fake_run(cases: Any, knowledge: CurrentKnowledge, llm: Any, workers: int = 4) -> list[Any]:
        seen.append(knowledge)
        return []

    NoModel.calls = 0
    monkeypatch.setattr(module, "run", fake_run)
    monkeypatch.setattr(pl, "make_llm", lambda *args, **kwargs: NoModel())
    argv = [
        "router_eval.py",
        "--out",
        str(tmp_path / "out"),
        "--only",
        "no-such-case",
        "--label",
        "т",
        *extra,
    ]
    monkeypatch.setattr(sys, "argv", argv)
    try:
        module.main()
    except SystemExit as exc:
        pytest.fail(f"router_eval exited: {exc.code}")
    assert NoModel.calls == 0
    return seen


def test_router_eval_with_notes_routes_on_the_seeded_cards_plus_the_notes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first, second = two_card_ids()
    items = [router(first, second), facilitator(first), router(second)]
    write_file(tmp_path / "notes", f"{first}.yaml", items[:2])
    write_file(tmp_path / "notes", f"{second}.yaml", items[2:])
    seen = main_with(tmp_path, monkeypatch, ["--notes", str(tmp_path / "notes")])
    assert len(seen) >= 1
    knowledge = seen[0]
    assert len(knowledge.cards) == 25
    assert {r.id: r for r in knowledge.memory} == {r.id: r for r in (as_record(i) for i in items)}
    assert knowledge.rev == 2


def test_router_eval_without_notes_routes_on_the_seeded_cards_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen = main_with(tmp_path, monkeypatch, [])
    assert len(seen) >= 1
    assert seen[0].memory == []
    assert seen[0].rev == 1
    assert len(seen[0].cards) == 25
