"""Compare a router-eval run with the base, case by case (task 307, slice product-router-eval).

Reads two finished `.json` runs of `scripts/router_eval.py` and writes `<X>.compare.md` beside the run:
the old cases (the ids of the base) against the base — regressions, fixed, missing, unavailable — and the
new cases of the 7 product cards. With `--repeats18 / --repeats25` it writes the shares of the ×5 repeats
instead. Pure reading: no model, no change to the scripts of task 302.

Run: `uv run python scripts/router_eval_compare.py --run <X>.json --base <base>.json`
     `uv run python scripts/router_eval_compare.py --repeats18 <dir> --repeats25 <dir>`
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

NEW_CARDS = ["customer-interviews", "demand-test", "positioning", "offer-design", "value-pricing",
             "traction-channels", "unit-economics"]  # fmt: skip
CHANGED_EXPECTATION = {"ot-2": "demand-test"}  # S1 added demand-test to its also_ok
COUNTED = ("positive", "tie")  # the kinds whose `expect` is the card measured; negatives count apart


def compare(
    run: dict[str, Any], base: dict[str, Any], old_ids: set[str], new_cards: list[str]
) -> dict[str, Any]:
    """Flow: index both runs by case → the old part against the base → the new part on its own."""
    now, before = _by_case(run), _by_case(base)
    return {"old": _old_part(now, before, old_ids), "new": _new_part(now, old_ids, new_cards)}


def _by_case(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(o["case_id"]): o for o in data.get("outcomes", [])}


def _down(outcome: dict[str, Any] | None) -> bool:
    return outcome is not None and outcome.get("action") == "unavailable"


def _old_part(
    now: dict[str, dict[str, Any]], before: dict[str, dict[str, Any]], old_ids: set[str]
) -> dict[str, Any]:
    present = sorted(cid for cid in old_ids if cid in now)
    down = [cid for cid in present if _down(now[cid]) or _down(before.get(cid))]
    graded = [cid for cid in present if cid not in down]
    both = [cid for cid in graded if cid in before]
    return {
        "n": len(graded),
        "first_now": sum(bool(now[cid]["first_ok"]) for cid in graded),
        "first_base": sum(bool(before[cid]["first_ok"]) for cid in both),
        "regressions": [cid for cid in both if before[cid]["first_ok"] and not now[cid]["first_ok"]],
        "fixed": [cid for cid in both if not before[cid]["first_ok"] and now[cid]["first_ok"]],
        "missing": sorted(cid for cid in old_ids if cid not in now),
        "unavailable": down,
        "changed_expectation": [
            cid
            for cid, card in CHANGED_EXPECTATION.items()
            if cid in graded and now[cid].get("first") == card
        ],
    }


def _new_part(now: dict[str, dict[str, Any]], old_ids: set[str], new_cards: list[str]) -> dict[str, Any]:
    new = [o for cid, o in sorted(now.items()) if cid not in old_ids]
    graded = [o for o in new if not _down(o)]
    measured = [o for o in graded if o.get("kind") in COUNTED]
    held = [o for o in measured if str(o["case_id"]).endswith("-3")]
    return {
        "n": len(measured),
        "first": sum(bool(o["first_ok"]) for o in measured),
        "offered": sum(bool(o["offered_ok"]) for o in measured),
        "unavailable": len(new) - len(graded),
        "held_out": _counts(held),
        "by_card": {card: _counts([o for o in measured if o.get("expect") == card]) for card in new_cards},
        "negatives_broken": [
            str(o["case_id"])
            for o in graded
            if o.get("kind") in ("negative", "tie") and not o.get("negative_ok", True)
        ],
    }


def _counts(outcomes: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "n": len(outcomes),
        "first": sum(bool(o["first_ok"]) for o in outcomes),
        "offered": sum(bool(o["offered_ok"]) for o in outcomes),
    }


def render(cmp: dict[str, Any], meta: dict[str, Any]) -> str:
    """Flow: head → old cases → new cases."""
    return "\n".join([*_head(meta), *_old_lines(cmp["old"]), *_new_lines(cmp["new"])]) + "\n"


def _head(meta: dict[str, Any]) -> list[str]:
    base = meta.get("base", "—")
    return [
        f"# Порівняння прогону {meta.get('stamp', '?')} з базою {base}",
        "",
        f"Прогін: «{meta.get('label', '')}», модель `{meta.get('model', '?')}`,"
        f" карток {meta.get('cards', '?')}.",
        "",
    ]


def _ids(ids: list[str]) -> str:
    return ", ".join(f"`{i}`" for i in ids) if ids else "немає"


def _old_lines(old: dict[str, Any]) -> list[str]:
    lines = [
        "## Старі випадки (ids бази)",
        "",
        f"- Першою (або справжня нічия): {old['first_now']} з {old['n']} тепер;"
        f" у базі — {old['first_base']}.",
        f"- Регреси (першою в базі, тепер ні): {_ids(old['regressions'])}.",
        f"- Виправлені (не першою в базі, тепер так): {_ids(old['fixed'])}.",
        f"- Немає в прогоні: {_ids(old['missing'])};"
        f" модель недоступна (поза знаменниками): {_ids(old['unavailable'])}.",
    ]
    lines += [
        f"- `{cid}` першою лише завдяки `{CHANGED_EXPECTATION[cid]}`, яку S1 додав у його `also_ok`:"
        " це зміна очікування, а не стабільність роутера."
        for cid in old["changed_expectation"]
    ]
    if old.get("absent_broken"):
        lines.append(f"- Запропоновано картку, якої не мало бути (`absent`): {_ids(old['absent_broken'])}.")
    return [*lines, ""]


def _new_lines(new: dict[str, Any]) -> list[str]:
    held = new["held_out"]
    lines = [
        "## Нові випадки (картки задачі 307)",
        "",
        f"- Позитивні й нічиї: першою {new['first']} з {new['n']},"
        f" серед запропонованих {new['offered']} з {new['n']}.",
        f"- Відкладена частина `*-3`: першою {held['first']} з {held['n']},"
        f" серед запропонованих {held['offered']} з {held['n']}.",
        f"- Hard negatives і нічиї, де заборонена картка стала першою: {_ids(new['negatives_broken'])}.",
        f"- Модель недоступна: {new['unavailable']}.",
        "",
        "| картка | випадків | першою | серед запропонованих |",
        "|---|---|---|---|",
    ]
    lines += [
        f"| `{card}` | {c['n']} | {c['first']} | {c['offered']} |" for card, c in new["by_card"].items()
    ]
    return [*lines, ""]


def shares(runs: list[dict[str, Any]]) -> dict[str, tuple[int, int]]:
    """Per case: (first, graded) over the runs; an unavailable answer is outside the denominator."""
    out: dict[str, tuple[int, int]] = {}
    for run in runs:
        for o in run.get("outcomes", []):
            if _down(o):
                out.setdefault(str(o["case_id"]), (0, 0))
                continue
            first, graded = out.get(str(o["case_id"]), (0, 0))
            out[str(o["case_id"])] = (first + bool(o["first_ok"]), graded + 1)
    return out


def summary_table(side18: dict[str, tuple[int, int]], side25: dict[str, tuple[int, int]]) -> str:
    rows = [
        "# Повтори ×5: частка «першою» на 18 і на 25 картках",
        "",
        "| випадок | 18 карток (`6091f88`) | 25 карток | позначка |",
        "|---|---|---|---|",
    ]
    for cid in sorted(set(side18) | set(side25)):
        mark = (
            f"на боці 18 оцінено без `{CHANGED_EXPECTATION[cid]}` в `also_ok`"
            if cid in CHANGED_EXPECTATION
            else ""
        )
        rows.append(f"| `{cid}` | {_share(side18.get(cid))} | {_share(side25.get(cid))} | {mark} |")
    return "\n".join(rows) + "\n"


def _share(value: tuple[int, int] | None) -> str:
    return "—" if value is None else f"{value[0]} з {value[1]}"


def _runs(folder: Path) -> list[dict[str, Any]]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(folder.glob("*.json"))]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path)
    parser.add_argument("--base", type=Path)
    parser.add_argument("--repeats18", type=Path)
    parser.add_argument("--repeats25", type=Path)
    args = parser.parse_args(argv)
    if args.repeats18 and args.repeats25:
        out = args.repeats18.parent / "summary.md"
        out.write_text(
            summary_table(shares(_runs(args.repeats18)), shares(_runs(args.repeats25))), encoding="utf-8"
        )
        print(f"записано: {out}")
        return 0
    if not (args.run and args.base):
        parser.error("--run and --base, or --repeats18 and --repeats25")
    run, base = (
        json.loads(args.run.read_text(encoding="utf-8")),
        json.loads(args.base.read_text(encoding="utf-8")),
    )
    cmp = compare(run, base, {str(o["case_id"]) for o in base.get("outcomes", [])}, NEW_CARDS)
    cmp["old"]["absent_broken"] = list(run.get("summary", {}).get("absent_broken", []))
    meta = {**run.get("meta", {}), "base": base.get("meta", {}).get("stamp", args.base.stem)}
    out = args.run.with_name(args.run.stem + ".compare.md")
    out.write_text(render(cmp, meta), encoding="utf-8")
    print(f"записано: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
