"""Live run of slice research-live (`-m live`): the owner's conversation #16–#30 again, through the product.

The owner's topic t-d824f508a729 is read at run time from the users bucket (ADC). His turns #1–#16 go into
a local topic as they are (no routing.json; the map — the bucket's items whose turn number is ≤ 16), then
his turns #17, #19 … #29 verbatim, one by one, through `workspace.reply` with `VertexLlm(search=True)`. The
record, before and after, with each answer's own evidence: `.engine/artifacts/research-live/<time>/`.
"""

import json
import os
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from thinkhow.access import CurrentUser
from thinkhow.facilitation import respond
from thinkhow.facilitation.types import ProblemMap
from thinkhow.knowledge import current, seed
from thinkhow.platform.config import load_settings
from thinkhow.platform.llm import make_llm
from thinkhow.platform.storage import LocalStorage
from thinkhow.workspace import Answered, Delta, TopicRef, reply, set_language
from thinkhow.workspace import conversation as conv_file

START = 16


@dataclass(frozen=True)
class Evidence:
    """What belongs to one answer: the router's new decisions, its research entries, its `llm_call` lines."""

    turn: int
    decisions: list[dict[str, Any]]
    research: list[dict[str, Any]]
    calls: list[dict[str, Any]]


def owner_turns(conv: conv_file.Conversation, start: int = START) -> list[conv_file.Turn]:
    """The person's turns after `start`, in order."""
    return [t for s in conv.sessions for t in s.turns if t.role == "user" and t.no > start]


def start_map(bucket_map: ProblemMap, start: int = START) -> ProblemMap:
    """The bucket's items whose turn number is ≤ `start` (a number, not text); no phase; last_turn start."""
    items = [item for item in bucket_map.items if _turn_no(item.turn) <= start]
    return ProblemMap(items=items, phase_id=None, last_turn=start)


def _turn_no(turn: str) -> int:
    """«t17» → 17: compared as a number, so «t3» is before «t16» (I2)."""
    return int(turn[1:])


def evidence(
    answer_turn: int,
    before: list[dict[str, Any]],
    after: list[dict[str, Any]],
    research: list[dict[str, Any]],
    log_text: str,
) -> Evidence:
    """One answer's evidence: routing.json's new tail, this answer's research entries, its llm_call lines."""
    calls = [json.loads(line) for line in log_text.splitlines() if '"llm_call"' in line]
    own = [entry for entry in research if entry["turn"] == answer_turn]
    return Evidence(answer_turn, after[len(before) :], own, calls)


ROOT = Path(__file__).resolve().parents[2]
CARDS = ROOT / "cards"
OUT = ROOT / ".engine" / "artifacts" / "research-live"
TOPIC = "gs://pocket-lawyer-431614-thinkhow-users/104839836105981044615/t-d824f508a729"
USER = CurrentUser(id="live-person", email="live@example.com", is_owner=False)
REF = TopicRef(USER.id, "t-0e5ea0000000")
IN_USD, OUT_USD, QUERY_USD = 2.2 / 1e6, 11 / 1e6, 14 / 1000  # PR-19, as in test_research_deep_live.py


def _cat(name: str) -> str:
    return subprocess.run(
        ["gcloud", "storage", "cat", f"{TOPIC}/{name}"], capture_output=True, check=True, text=True
    ).stdout


def _price(calls: list[dict[str, Any]]) -> str:
    model = sum(
        c["prompt_tokens"] * IN_USD + (c["output_tokens"] + c["thought_tokens"]) * OUT_USD for c in calls
    )
    queries = sum(c["queries"] for c in calls)
    seconds = sum(c["latency_ms"] for c in calls) / 1000
    usd = f"${model:.3f} модель + ${queries * QUERY_USD:.3f} пошук понад безплатні"
    return f"{len(calls)} викликів, {seconds:.1f} с моделі, {queries} пошукових запитів; {usd}"


def _decision_line(ev: Evidence, card: str | None) -> str:
    if not ev.decisions:
        return f"без нового рішення роутера (картка {card})"
    return "; ".join(
        f"{d['kind']} {d.get('card_id') or ', '.join(c['card_id'] for c in d['candidates'])}"
        for d in ev.decisions
    )


def _section(
    turn: conv_file.Turn, answer: str, ev: Evidence, card: str | None, facts: list[str]
) -> list[str]:
    lines = [f"### #{turn.no} Людина", "", turn.text, "", f"### #{ev.turn} ThinkHow", "", answer, ""]
    lines += [f"- роутер: {_decision_line(ev, card)}"]
    for entry in ev.research:
        urls = [s["url"] for s in entry["sources"]]
        lines += [f"- дослідження {entry['depth']}: запити {entry['queries']}; джерела {urls}"]
    if not ev.research:
        lines += ["- дослідження: не шукала"]
    lines += [f"- нові пункти fact: {facts}", f"- {_price(ev.calls)}", ""]
    return lines


def _not_own(ev: Evidence) -> list[str]:
    """I1: research entries carry the answer's number; router decisions the person's turn before it."""
    bad = [f"#{ev.turn}: research turn {e['turn']}" for e in ev.research if e["turn"] != ev.turn]
    return bad + [f"#{ev.turn}: decision turn {d['turn']}" for d in ev.decisions if d["turn"] != ev.turn - 1]


@pytest.mark.live
def test_the_owners_conversation_again_through_the_product(
    tmp_path: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    storage = LocalStorage(tmp_path)
    seed(storage, CARDS)
    knowledge = current(storage)
    environ = {
        **os.environ,
        "THINKHOW_LOCAL": "false",
        "THINKHOW_USERS_BUCKET": "-",
        "THINKHOW_SYSTEM_BUCKET": "-",
        "THINKHOW_OWNER_EMAIL": "-",
    }
    llm = make_llm(load_settings(environ), lambda *_: "", search=True)

    def facilitate(ctx: Any) -> Any:
        return respond(ctx, knowledge, llm)

    set_language(storage, USER, "uk-UA")
    owner = conv_file.parse(_cat("conversation.md"))
    first = start_map(ProblemMap.model_validate_json(_cat("map.json")))
    ids = [item.id for item in first.items]
    assert "i3" in ids and "i10" in ids and all(_turn_no(i.turn) <= START for i in first.items), ids
    turns = owner_turns(owner)
    stamps = [t.at for s in owner.sessions for t in s.turns if t.no >= START]
    assert all(b - a < timedelta(hours=24) for a, b in zip(stamps, stamps[1:], strict=False)), stamps
    history = [t for s in owner.sessions for t in s.turns if t.no <= START]
    base = f"{REF.uid}/{REF.topic_id}"
    conv = conv_file.Conversation(owner.title, [conv_file.SessionDoc(no=1, turns=history)])
    storage.write("users", f"{base}/conversation.md", conv_file.render(conv).encode(), "text/markdown")
    storage.write("users", f"{base}/map.json", first.model_dump_json().encode(), "application/json")

    def read(name: str, empty: str) -> Any:
        return json.loads(storage.read("users", f"{base}/{name}") or empty.encode())

    capfd.readouterr()
    after_lines: list[str] = []
    failed: str | None = None
    problems: list[str] = []
    for turn in turns:
        before = read("routing.json", '{"decisions": []}')["decisions"]
        facts_before = {i["id"] for i in read("map.json", "{}").get("items", []) if i["type"] == "fact"}
        events = list(reply(storage, facilitate, USER, REF, turn.text, turn.at))
        log_text = capfd.readouterr().out
        after = read("routing.json", '{"decisions": []}')["decisions"]
        if after[: len(before)] != before:
            problems.append(f"#{turn.no}: routing.json changed its start")
        if not isinstance(events[-1], Answered):
            failed = f"#{turn.no}: {events[-1]}"
            after_lines += [
                f"### #{turn.no} Людина",
                "",
                turn.text,
                "",
                f"**Відповіді немає: {events[-1]}**",
                "",
            ]
            break
        ev = evidence(
            events[-1].turn_no, before, after, read("research.json", '{"entries": []}')["entries"], log_text
        )
        problems += _not_own(ev)
        answer = "".join(e.text for e in events if isinstance(e, Delta))
        card = next((d["card_id"] for d in reversed(after) if d["kind"] == "choose"), None)
        items = read("map.json", "{}").get("items", [])
        facts = [i["text"] for i in items if i["type"] == "fact" and i["id"] not in facts_before]
        after_lines += _section(turn, answer, ev, card, facts)
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H%M%SZ")
    folder = OUT / stamp
    folder.mkdir(parents=True, exist_ok=True)
    before_lines = []
    for t in (t for s in owner.sessions for t in s.turns if t.no >= START):
        who = "Людина" if t.role == "user" else "ThinkHow (тоді)"
        before_lines += [f"### #{t.no} {who}", "", t.text, ""]
    lines = [
        "# Розмова власника #16–#30 заново (задача 303, S4)",
        "",
        f"Прогін: {stamp}; тема `t-d824f508a729`.",
        "",
    ]
    lines += [
        f"Початкова карта (пункти з номером репліки ≤ 16): {ids}; `routing.json` — немає (роутер на #17).",
        "",
    ]
    lines += [
        "## До (як у bucket, 2026-10-24)",
        "",
        *before_lines,
        "## Після (продукт з дослідженням)",
        "",
        *after_lines,
    ]
    (folder / "conversation.md").write_text("\n".join(lines), encoding="utf-8")
    print(folder / "conversation.md")
    assert failed is None, failed
    assert not problems, problems
