"""The router on the set of situations (task 302, slice router-eval): how often the expected card is first and
among the offered, through the real model on `eu`.

Run: `PYTHONPATH=src uv run python scripts/router_eval.py [--cases <yaml>] [--out <dir>] [--label <text>]
[--only <id>…]`. Knowledge from cards/ in a temporary local folder; one `route` call per situation; a
report .md and .json in .engine/artifacts/router-eval/, never overwritten. The context of a situation, the
measures and the summary are plain functions; `run` takes the model port and the Knowledge as parameters.
"""

import argparse
import hashlib
import json
import subprocess
import tempfile
import threading
import time
from collections import Counter
from collections.abc import Iterator, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

from thinkhow.facilitation import (
    Candidate,
    Decision,
    FacilitationContext,
    FacilitationError,
    ProblemMap,
    RouterAnswer,
    Turn,
    route,
)
from thinkhow.knowledge import CurrentKnowledge, current, seed
from thinkhow.platform import llm as model
from thinkhow.platform import log
from thinkhow.platform.config import Settings
from thinkhow.platform.llm import LlmUnavailable
from thinkhow.platform.storage import LocalStorage

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "tests" / "fixtures" / "routing" / "cases.yaml"
OUT = ROOT / ".engine" / "artifacts" / "router-eval"
LANGUAGE = "Українська (uk-UA)"
REFERENCE = 0.85  # research 01 §10.2 — a line of comparison only, PROVISIONAL (no owner threshold)
PAUSE_S = 30


@dataclass
class Outcome:
    """The measures of one situation (contract Seam `router_eval.py`)."""

    case_id: str
    kind: str
    expect: str
    action: str  # offer | ask | choose | invalid | unavailable
    first: str | None
    offered: list[str]
    first_ok: bool
    offered_ok: bool
    negative_ok: bool
    absent_ok: bool
    reply: str = ""
    reason: str = ""
    profile: dict[str, str] = field(default_factory=dict)


def load_cases(path: Path = CASES) -> list[dict[str, Any]]:
    """The situations of the set, in file order."""
    return list(yaml.safe_load(path.read_text(encoding="utf-8"))["cases"])


def routing_of(case: dict[str, Any]) -> tuple[Decision, ...]:
    """The routing.json decisions of this situation (other: offer; midway: offer, choose, end)."""
    history = len(case.get("history", []))
    if case["kind"] == "other":
        return (_decision(max(history - 1, 1), "offer", list(case["offered"]), None, None),)
    if case["kind"] == "midway":
        cid, end = case["ended"]["card_id"], case["ended"]["end"]
        return (
            _decision(1, "offer", [cid], None, None),
            _decision(max(history - 1, 1), "choose", [], cid, None),
            _decision(max(history - 1, 1), "end", [], cid, end),
        )
    return ()


def _decision(turn: int, kind: str, ids: list[str], card_id: str | None, end: str | None) -> Decision:
    return Decision.model_validate(
        {
            "turn": turn,
            "rev": {"rev": 1, "n": 0},
            "kind": kind,
            "profile": None,
            "candidates": [Candidate(card_id=c, why="(з набору ситуацій)").model_dump() for c in ids],
            "card_id": card_id,
            "end": end,
            "why": "(з набору ситуацій)",
        }
    )


def context_of(case: dict[str, Any]) -> FacilitationContext:
    """The router's context of a situation, as the product passes it."""
    history = [Turn(t["role"], t["text"]) for t in case.get("history", [])]
    return FacilitationContext(
        "pre-mortem",
        history,
        ProblemMap(last_turn=len(history)),
        len(history) + 1,
        case["text"].strip(),
        LANGUAGE,
        routing_of(case),
    )


def measure(case: dict[str, Any], answer: RouterAnswer) -> Outcome:
    """first / first_ok / offered_ok / negative_ok / absent_ok of one answer (Q1; ask by its ranking)."""
    offered = [c.card_id for c in answer.candidates]
    if answer.action == "choose" and answer.card_id is not None:
        offered = [answer.card_id, *[c for c in offered if c != answer.card_id]]
    first = offered[0] if offered else None
    return Outcome(
        case_id=case["id"],
        kind=case["kind"],
        expect=case["expect"],
        action=answer.action,
        first=first,
        offered=offered,
        first_ok=first is not None and first in {case["expect"], *case.get("also_ok", [])},
        offered_ok=case["expect"] in offered,
        negative_ok=first not in case.get("not_first", []),
        absent_ok=not set(case.get("absent", [])) & set(offered),
        reply=answer.reply or "",
        profile=answer.profile.model_dump(),
    )


def invalid(case: dict[str, Any], reason: str) -> Outcome:
    """The router's answer stayed invalid (FacilitationError): a miss in the denominators."""
    return Outcome(
        case["id"], case["kind"], case["expect"], "invalid", None, [], False, False, True, True, reason=reason
    )


def unavailable(case: dict[str, Any], reason: str) -> Outcome:
    """The model was unavailable (LlmUnavailable): outside the denominators."""
    return Outcome(
        case["id"],
        case["kind"],
        case["expect"],
        "unavailable",
        None,
        [],
        False,
        False,
        True,
        True,
        reason=reason,
    )


def run(
    cases: list[dict[str, Any]], knowledge: CurrentKnowledge, llm: model.Llm, workers: int = 4
) -> list[Outcome]:
    """One route call per situation in a pool; the log's request id is the situation's id; ordered by id."""
    with ThreadPoolExecutor(max_workers=workers) as pool:
        outcomes = list(pool.map(lambda c: _one(c, knowledge, llm), cases))
    return sorted(outcomes, key=lambda o: o.case_id)


def _one(case: dict[str, Any], knowledge: CurrentKnowledge, llm: model.Llm) -> Outcome:
    token = log.request_id.set(case["id"])
    try:
        for attempt in (1, 2):
            try:
                return measure(case, route(context_of(case), knowledge, llm))
            except FacilitationError as exc:
                return invalid(case, str(exc))
            except LlmUnavailable as exc:
                if attempt == 2:
                    return unavailable(case, str(exc))
                time.sleep(PAUSE_S)
        raise AssertionError("unreachable")
    finally:
        log.request_id.reset(token)


def held_out(case_id: str) -> bool:
    """The third positive case of each card (`*-3`): no confusion is diagnosed on it (Q6)."""
    return case_id.endswith("-3")


def summary(outcomes: list[Outcome], card_ids: list[str]) -> dict[str, Any]:
    """The report's numbers: per card, held-out apart, confusions, asks, invalid, unavailable."""
    graded = [o for o in outcomes if o.action != "unavailable"]
    by_card = {
        cid: {
            "n": len(mine := [o for o in graded if o.expect == cid and o.kind == "positive"]),
            "first": sum(o.first_ok for o in mine),
            "offered": sum(o.offered_ok for o in mine),
            "held_out_first": sum(o.first_ok for o in mine if held_out(o.case_id)),
            "held_out_offered": sum(o.offered_ok for o in mine if held_out(o.case_id)),
        }
        for cid in card_ids
    }
    confusions = Counter(
        f"{o.expect} → {o.first or o.action}"
        for o in graded
        if not o.first_ok and o.action not in ("invalid",) and not held_out(o.case_id)
    )
    held = [o for o in graded if held_out(o.case_id)]
    rest = [o for o in graded if not held_out(o.case_id)]
    return {
        "cases": len(outcomes),
        "graded": len(graded),
        "first_ok": sum(o.first_ok for o in graded),
        "offered_ok": sum(o.offered_ok for o in graded),
        "held_out": {
            "n": len(held),
            "first": sum(o.first_ok for o in held),
            "offered": sum(o.offered_ok for o in held),
        },
        "rest": {
            "n": len(rest),
            "first": sum(o.first_ok for o in rest),
            "offered": sum(o.offered_ok for o in rest),
        },
        "negatives_broken": [
            o.case_id for o in graded if o.kind in ("negative", "tie") and not o.negative_ok
        ],
        "absent_broken": [o.case_id for o in graded if not o.absent_ok],
        "asks": sum(o.action == "ask" for o in outcomes),
        "first_ok_via_ask": sum(o.first_ok for o in outcomes if o.action == "ask"),
        "invalid": sum(o.action == "invalid" for o in outcomes),
        "unavailable": sum(o.action == "unavailable" for o in outcomes),
        "by_card": by_card,
        "confusions": confusions.most_common(),
    }


def _pct(part: int, whole: int) -> str:
    return f"{part} з {whole} ({part / whole:.0%})" if whole else "0 з 0"


def report(outcomes: list[Outcome], summ: dict[str, Any], meta: dict[str, Any], calls: list[str]) -> str:
    g, held, rest = summ["graded"], summ["held_out"], summ["rest"]
    lines = [
        f"# Роутер на наборі ситуацій — {meta['label']}",
        "",
        f"Прогін {meta['stamp']}; модель продукту — `{meta['model']}` (Vertex `eu`); Знання — 18 карток",
        f"з `cards/` (ревізія {meta['rev']}); набір — `tests/fixtures/routing/cases.yaml`",
        f"(blob `{meta['cases_blob']}`), {summ['cases']} ситуацій;",
        f"хеш `cards/` — `{meta['cards_hash'][:12]}`.",
        "",
        f"- Очікувана картка (або справжня нічия) **перша**: {_pct(summ['first_ok'], g)};",
        f"  орієнтир research 01 §10.2 — {REFERENCE:.0%} (PROVISIONAL, не поріг).",
        f"- Очікувана картка **серед запропонованих**: {_pct(summ['offered_ok'], g)}.",
        f"- Відкладена частина (`*-3`, незалежна перевірка): перша {_pct(held['first'], held['n'])},"
        f" серед запропонованих {_pct(held['offered'], held['n'])}.",
        f"- Решта набору (той самий набір — не незалежна перевірка): перша {_pct(rest['first'], rest['n'])},"
        f" серед запропонованих {_pct(rest['offered'], rest['n'])}.",
        f"- Hard negatives і нічиї, де заборонена картка стала першою: {len(summ['negatives_broken'])} "
        f"{summ['negatives_broken'] or ''}".rstrip(),
        f"- Картка, якої не має бути серед запропонованих, запропонована: {len(summ['absent_broken'])} "
        f"{summ['absent_broken'] or ''}".rstrip(),
        f"- Уточнювальне питання замість пропозиції: {summ['asks']} (з них перша правильна за ранжуванням: "
        f"{summ['first_ok_via_ask']}); невалідних: {summ['invalid']}; недоступна модель: "
        f"{summ['unavailable']} (поза знаменниками).",
        f"- Викликів моделі (обгортка порту): {meta['model_calls']}; рядків `llm_call`: {len(calls)}.",
        "",
        "## По картках (позитивні випадки)",
        "",
        "| картка | випадків | перша | серед запропонованих | `*-3` перша | `*-3` серед |",
        "|---|---|---|---|---|---|",
    ]
    for cid, row in summ["by_card"].items():
        lines.append(
            f"| `{cid}` | {row['n']} | {row['first']} | {row['offered']} | {row['held_out_first']} | "
            f"{row['held_out_offered']} |"
        )
    lines += ["", "## Плутанини поза відкладеною частиною (очікували → перша)", ""]
    lines += [f"- `{k}` — {v}" for k, v in summ["confusions"]] or ["- немає"]
    lines += [
        "",
        "## Кожна ситуація",
        "",
        "| id | вид | очікували | дія | перша | запропоновано | ✓ перша | ✓ серед |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for o in outcomes:
        lines.append(
            f"| {o.case_id} | {o.kind} | `{o.expect}` | {o.action} | `{o.first}` | {', '.join(o.offered)} | "
            f"{'так' if o.first_ok else 'ні'} | {'так' if o.offered_ok else 'ні'} |"
        )
    lines += ["", "## Рядки журналу `llm_call`", "", "```", *calls, "```", ""]
    return "\n".join(lines)


@dataclass
class CountingLlm:
    """The model port with a count of calls, independent of the log (Seam 6)."""

    inner: model.Llm
    calls: int = 0
    lock: threading.Lock = field(default_factory=threading.Lock)

    def _count(self) -> None:
        with self.lock:
            self.calls += 1

    def generate_json(
        self, system: str, contents: Sequence[model.Turn], schema: type[Any], rev: model.KnowledgeRev | None
    ) -> Any:
        self._count()
        return self.inner.generate_json(system, contents, schema, rev)

    def stream_json(
        self,
        system: str,
        contents: Sequence[model.Turn],
        schema: type[BaseModel],
        rev: model.KnowledgeRev | None,
    ) -> Iterator[model.ReplyDelta | model.Done]:
        self._count()
        return self.inner.stream_json(system, contents, schema, rev)


def cards_hash(folder: Path) -> str:
    digest = hashlib.sha256()
    for f in sorted(folder.glob("*.yaml")):
        digest.update(f.name.encode() + b"\0" + f.read_bytes())
    return digest.hexdigest()


def product_settings(name: str = "gemini-4-argon") -> Settings:
    return Settings(local=False, model=name, users_bucket="-", system_bucket="-", owner_email="-")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, default=CASES)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--label", default="прогін")
    parser.add_argument("--only", nargs="*", default=None)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    cases = [c for c in load_cases(args.cases) if not args.only or c["id"] in args.only]
    storage = LocalStorage(Path(tempfile.mkdtemp(prefix="thinkhow-eval-")))
    seed(storage, ROOT / "cards")
    knowledge = current(storage)
    settings = product_settings()
    llm = CountingLlm(model.make_llm(settings, lambda *_: ""))
    log_lines: list[str] = []
    original = model.log_event

    def recording(event: str, **fields: Any) -> None:
        line = {"severity": "INFO", **fields, "event": event, "request_id": log.request_id.get()}
        log_lines.append(json.dumps(line, ensure_ascii=False, default=str))

    model.log_event = recording  # the llm module's own name for the log (Q5)
    try:
        outcomes = run(cases, knowledge, llm, args.workers)
        down = [o for o in outcomes if o.action == "unavailable"]
        if len(down) > len(cases) / 10:  # technical rule of the run, not a product threshold
            again = {
                o.case_id: o
                for o in run([c for c in cases if c["id"] in {d.case_id for d in down}], knowledge, llm, 1)
            }
            outcomes = sorted([again.get(o.case_id, o) for o in outcomes], key=lambda o: o.case_id)
    finally:
        model.log_event = original
    calls = [line for line in log_lines if '"llm_call"' in line]
    summ = summary(outcomes, sorted(knowledge.cards))
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H%M%SZ")
    blob = subprocess.run(["git", "hash-object", str(args.cases)], capture_output=True, text=True, check=True)
    meta = {
        "label": args.label,
        "stamp": stamp,
        "model": settings.model,
        "rev": {"rev": knowledge.rev, "n": knowledge.n},
        "cases_blob": blob.stdout.strip(),
        "cards_hash": cards_hash(ROOT / "cards"),
        "model_calls": llm.calls,
    }
    args.out.mkdir(parents=True, exist_ok=True)
    md = args.out / f"{stamp}.md"
    with md.open("x", encoding="utf-8") as out:
        out.write(report(outcomes, summ, meta, calls))
    with (args.out / f"{stamp}.json").open("x", encoding="utf-8") as out:
        json.dump(
            {"meta": meta, "summary": summ, "outcomes": [asdict(o) for o in outcomes], "llm_call": calls},
            out,
            ensure_ascii=False,
            indent=1,
        )
    print(md)
    print(
        json.dumps({k: v for k, v in summ.items() if k not in ("by_card", "confusions")}, ensure_ascii=False)
    )


if __name__ == "__main__":
    main()
