"""Helpers of the contract tests of product-router-eval (slice tester; from the contract, not the code).

Fixtures of `router_eval.py` runs are written by hand in the shape of its `.json` (`meta`, `summary`,
`outcomes[*]` with `case_id`, `kind`, `expect`, `action`, `first`, `offered`, `first_ok`, `offered_ok`,
`negative_ok`, `absent_ok`). The AC5 rule of Seam 2 / I3 is `card_passes`: the rows of a card are the rows
whose «цільова» is the card; columns are read by the header's names, not by position.
"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
ARTIFACTS = ROOT / ".engine" / "artifacts"
NEW_CARDS = ["customer-interviews", "demand-test", "positioning", "offer-design", "value-pricing",
             "traction-channels", "unit-economics"]  # fmt: skip
SEEDED_MARK = "вели без вибору роутером"

_loaded: dict[str, ModuleType] = {}


def script(name: str) -> ModuleType:
    if name not in _loaded:
        spec = importlib.util.spec_from_file_location(f"pre_script_{name}", ROOT / "scripts" / f"{name}.py")
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        _loaded[name] = module
    return _loaded[name]


def cmp_module() -> ModuleType:
    return script("router_eval_compare")


def oc(
    case_id: str,
    first_ok: bool = True,
    *,
    kind: str = "positive",
    expect: str = "consider-opposite",
    action: str = "offer",
    first: str | None = None,
    offered_ok: bool | None = None,
    negative_ok: bool = True,
    absent_ok: bool = True,
) -> dict[str, Any]:
    """One outcome of a run. `unavailable` and `invalid` carry first_ok/offered_ok False, as a miss."""
    if action in ("unavailable", "invalid"):
        first_ok = False
        offered_ok = False if offered_ok is None else offered_ok
    offered_ok = first_ok if offered_ok is None else offered_ok
    top = first if first is not None else (expect if first_ok else "five-whys")
    return {
        "case_id": case_id,
        "kind": kind,
        "expect": expect,
        "action": action,
        "first": top if action not in ("unavailable", "invalid") else None,
        "offered": [top] if action not in ("unavailable", "invalid") else [],
        "first_ok": first_ok,
        "offered_ok": offered_ok,
        "negative_ok": negative_ok,
        "absent_ok": absent_ok,
        "reply": "",
        "reason": "",
    }


def run_json(
    outcomes: list[dict[str, Any]],
    stamp: str = "2026-10-26T010203Z",
    cards: int = 25,
    absent_broken: list[str] | None = None,
) -> dict[str, Any]:
    graded = [o for o in outcomes if o["action"] != "unavailable"]
    return {
        "meta": {
            "label": "fixture",
            "stamp": stamp,
            "model": "gemini-4-argon",
            "cards": cards,
            "model_calls": len(outcomes),
        },
        "summary": {
            "cases": len(outcomes),
            "graded": len(graded),
            "first_ok": sum(o["first_ok"] for o in graded),
            "offered_ok": sum(o["offered_ok"] for o in graded),
            "held_out": {"n": 0, "first": 0, "offered": 0},
            "rest": {
                "n": len(graded),
                "first": sum(o["first_ok"] for o in graded),
                "offered": sum(o["offered_ok"] for o in graded),
            },
            "negatives_broken": [
                o["case_id"] for o in graded if o["kind"] in ("negative", "tie") and not o["negative_ok"]
            ],
            "absent_broken": list(absent_broken or []),
            "asks": 0,
            "first_ok_via_ask": 0,
            "invalid": sum(o["action"] == "invalid" for o in outcomes),
            "unavailable": len(outcomes) - len(graded),
            "by_card": {},
        },
        "outcomes": outcomes,
        "llm_call": [],
    }


def write_json(path: Path, data: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return path


def run_main(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "router_eval_compare.py"), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _plain(cell: str) -> str:
    return cell.strip().strip("`").strip()


def index_rows(index_text: str) -> list[dict[str, str]]:
    """The rows of an `index.md` table, as {header name: cell}, backticks stripped."""
    lines = [ln for ln in index_text.splitlines() if ln.strip().startswith("|")]
    if not lines:
        return []
    header = [_plain(c) for c in _cells(lines[0])]
    rows = []
    for ln in lines[1:]:
        cells = _cells(ln)
        if all(set(c) <= {"-", ":"} for c in cells):
            continue
        rows.append({name: _plain(cells[i]) if i < len(cells) else "" for i, name in enumerate(header)})
    return rows


def card_passes(index_text: str, card: str) -> bool:
    """Seam 2 / I3: some row with «цільова» = card has «вели» = card, «запропоновано» = так, «end: done» = так
    and no mark «вели без вибору роутером»."""
    return any(
        r.get("цільова") == card
        and r.get("вели") == card
        and r.get("запропоновано") == "так"
        and r.get("end: done") == "так"
        and SEEDED_MARK not in r.get("позначки", "")
        for r in index_rows(index_text)
    )


def card_has_row(index_text: str, card: str) -> bool:
    return any(r.get("цільова") == card for r in index_rows(index_text))


def row_of(table: str, case_id: str) -> list[str]:
    for ln in table.splitlines():
        if ln.strip().startswith("|") and case_id in _cells(ln)[0]:
            return _cells(ln)
    raise AssertionError(f"no row for {case_id} in:\n{table}")


def side_cell(table: str, case_id: str, side: str) -> str:
    """The cell of `case_id`'s row under the column of one side: the header names `side` ("18" or "25")
    and not the other one. Several such columns are joined (a side may have more than one)."""
    other = "25" if side == "18" else "18"
    header = next(_cells(ln) for ln in table.splitlines() if ln.strip().startswith("|"))
    cols = [i for i, c in enumerate(header) if side in c and other not in c]
    assert cols, header
    row = row_of(table, case_id)
    return " ".join(row[i] for i in cols if i < len(row))
