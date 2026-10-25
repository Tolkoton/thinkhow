"""Helpers for the product-cards contract tests (slice tester; built from the contract, not the code).

- the 18 ids of task 302, the 7 new ids of task 307 and their case prefixes (slice «Seam», «Goal» 1);
- `load(cid)` / `strings(node)` / `leading_comment(cid)`: the real `cards/<cid>.yaml`;
- `cases()`: the real `tests/fixtures/routing/cases.yaml`; `old_text(path)`: a file at commit 6091f88;
- `normalise`: the detector's own normalisation from `tests/live/test_router_live.py` (Seam 3).
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[3]
CARDS = ROOT / "cards"
CASES = ROOT / "tests" / "fixtures" / "routing" / "cases.yaml"
BASE = "6091f88"

OLD_IDS = [
    "first-principles", "issue-tree", "complexity-sensemaking", "five-whys", "is-is-not", "wrap-decision",
    "weighted-matrix", "reversible-doors", "evaporating-cloud", "pre-mortem", "consider-opposite",
    "socratic-questioning", "scamper", "mental-contrasting", "reflective-cycle", "goal-to-plan",
    "jobs-to-be-done", "opportunity-tree",
]  # fmt: skip
NEW_IDS = [
    "customer-interviews", "demand-test", "positioning", "offer-design", "value-pricing", "traction-channels",
    "unit-economics",
]  # fmt: skip
ALL_IDS = OLD_IDS + NEW_IDS
PREFIX = {
    "ci": "customer-interviews",
    "dt": "demand-test",
    "pos": "positioning",
    "of": "offer-design",
    "vp": "value-pricing",
    "tc": "traction-channels",
    "ue": "unit-economics",
}


def card_file(cid: str) -> Path:
    path = CARDS / f"{cid}.yaml"
    assert path.is_file(), f"cards/{cid}.yaml is missing"
    return path


def load(cid: str) -> Any:
    return yaml.safe_load(card_file(cid).read_text(encoding="utf-8"))


def all_card_ids() -> list[str]:
    """Every card of `cards/`; the 25 ids of the goal must be among them."""
    ids = sorted(p.stem for p in CARDS.glob("*.yaml"))
    missing = [cid for cid in ALL_IDS if cid not in ids]
    assert not missing, f"cards/ lacks {missing}"
    return ids


def strings(node: Any) -> list[str]:
    if isinstance(node, str):
        return [node]
    if isinstance(node, dict):
        return [s for value in node.values() for s in strings(value)]
    if isinstance(node, list):
        return [s for value in node for s in strings(value)]
    return []


def leading_comment(cid: str) -> str:
    """The comment at the top of the file: every `#` line before the first other line."""
    lines = []
    for line in card_file(cid).read_text(encoding="utf-8").splitlines():
        if not line.lstrip().startswith("#"):
            break
        lines.append(line)
    return "\n".join(lines)


def cases() -> list[dict[str, Any]]:
    data = yaml.safe_load(CASES.read_text(encoding="utf-8"))
    loaded: list[dict[str, Any]] = data["cases"]
    return loaded


def old_text(path: str) -> str:
    return subprocess.run(
        ["git", "show", f"{BASE}:{path}"], cwd=ROOT, capture_output=True, check=True, text=True
    ).stdout


def old_cases() -> list[dict[str, Any]]:
    loaded: list[dict[str, Any]] = yaml.safe_load(old_text("tests/fixtures/routing/cases.yaml"))["cases"]
    return loaded


def normalise() -> Callable[[str], str]:
    name = "pc_router_live"
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, ROOT / "tests" / "live" / "test_router_live.py")
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name].normalise  # type: ignore[no-any-return]
