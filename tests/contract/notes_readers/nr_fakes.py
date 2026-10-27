"""Helpers for the notes-readers contract tests (slice tester; built from the contract, not the code).

- ALPHA, BETA: the very cards of spoken_replies/sr_fakes.py (same values, rebuilt by hand), so the captured
  oracle `spoken_replies/sr_oracle.py` (commit cefcb02, before this slice) is the byte sample of Seam 3.
- GAMMA: a third card, for «not in c» (Seam 1).
- ORACLE: that captured dict, loaded by path (it lives in another test directory).
- note / legacy: memory records built by hand; `legacy` is parsed from JSON without `audience` (old record).
- section / note_lines / memory_section: cut an instruction the way the contract names its parts.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

from thinkhow.facilitation.route import CARDS_HEAD
from thinkhow.knowledge import Card, CurrentKnowledge, MemoryRecord

HERE = Path(__file__).resolve().parent

# The rule line of the contract («Seam (contract)», second item), copied word for word.
RULE = (
    "Рядки «Досвід:» біля картки — що помітили в розмовах інших людей: коли цей спосіб справді допомагав"
    " і з чим його плутають; враховуй їх, обираючи, але не називай людині."
)
MEMORY_HEAD = "# Пам'ять досвіду\n"
LANGUAGES: tuple[str | None, ...] = (None, "Polski (pl-PL)", "日本語 (ja-JP)")


def _load_oracle() -> dict[str, str]:
    name = "nr_sr_oracle"
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, HERE.parent / "spoken_replies" / "sr_oracle.py")
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    oracle: dict[str, str] = sys.modules[name].ORACLE
    return oracle


ORACLE = _load_oracle()


def _phase(pid: str) -> dict[str, Any]:
    return {
        "id": pid,
        "title": f"Фаза {pid}",
        "goal": f"мета {pid}",
        "how": [f"як {pid}"],
        "exit": f"вихід {pid}",
    }


def card(cid: str, phase_ids: Iterable[str], method: str | None = None) -> Card:
    data: dict[str, Any] = {
        "id": cid,
        "title": f"Картка {cid}",
        "router": {
            "needs": f"потреба {cid}",
            "when_yes": [f"так {cid}"],
            "when_no": [f"ні {cid}"],
            "signals": [f"сигнал {cid}"],
        },
        "facilitator": {
            "purpose": f"навіщо {cid}",
            "stance": f"позиція {cid}",
            "needs": f"на вході {cid}",
            "phases": [_phase(p) for p in phase_ids],
            "ending": f"кінець {cid}",
            "traps": [{"name": f"пастка {cid}", "text": f"текст пастки {cid}"}],
            "pairs_well": f"пара {cid}",
        },
    }
    if method is not None:
        data["method"] = method
    return Card.model_validate(data)


ALPHA = card("alpha", ["a_one", "a_two"])
BETA = card("beta", ["b_one"], method="Метод бета (Автор, 1999)")
GAMMA = card("gamma", ["g_one"])


def knowledge(cards: Sequence[Card], memory: Sequence[MemoryRecord]) -> CurrentKnowledge:
    return CurrentKnowledge(rev=3, n=7, cards={c.id: c for c in cards}, memory=list(memory))


def note(mid: str, cards: list[str], audience: str, title: str | None = None, **kw: str) -> MemoryRecord:
    tag = title or f"Нотатка {mid}"
    return MemoryRecord.model_validate(
        {
            "id": mid,
            "title": tag,
            "cards": cards,
            "noticed": kw.get("noticed", f"помітили {mid}"),
            "do": kw.get("do", f"робити {mid}"),
            "basis": kw.get("basis", f"підстава {mid}"),
            "audience": audience,
        }
    )


def legacy(mid: str, cards: list[str]) -> MemoryRecord:
    """A record as stored before learning-loop S1: JSON with no `audience` key."""
    raw = {
        "id": mid,
        "title": f"Стара нотатка {mid}",
        "cards": cards,
        "noticed": f"помітили {mid}",
        "do": f"робити {mid}",
        "basis": f"підстава {mid}",
    }
    return MemoryRecord.model_validate_json(json.dumps(raw, ensure_ascii=False))


def line_of(rec: MemoryRecord) -> str:
    """The router note line of the contract, `- <title>. <noticed> <do>`, for a record with no line breaks."""
    return f"- {rec.title}. {rec.noticed} {rec.do}"


def section(instruction: str, card_id: str) -> str:
    """The router instruction's part for one card: from its `### <id> — ` line to the next `### ` line."""
    lines = instruction[instruction.index(CARDS_HEAD) :].split("\n")
    start = next(i for i, ln in enumerate(lines) if ln.startswith(f"### {card_id} — "))
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("### ")), len(lines))
    return "\n".join(lines[start:end])


def note_lines(sec: str) -> list[str]:
    """The `- …` lines that follow the `Досвід:` line of a card's section (none: empty)."""
    lines = sec.split("\n")
    if "Досвід:" not in lines:
        return []
    out = []
    for ln in lines[lines.index("Досвід:") + 1 :]:
        if not ln.startswith("- "):
            break
        out.append(ln)
    return out


def before_experience(sec: str) -> str:
    """The card half of a section: the lines before `Досвід:` (all when none), blank tail cut."""
    lines = sec.split("\n")
    if "Досвід:" in lines:
        lines = lines[: lines.index("Досвід:")]
    return "\n".join(lines).rstrip("\n")


def memory_section(system: str) -> str:
    """What follows «# Пам'ять досвіду» in the facilitator's system instruction."""
    return system[system.index(MEMORY_HEAD) + len(MEMORY_HEAD) :]
