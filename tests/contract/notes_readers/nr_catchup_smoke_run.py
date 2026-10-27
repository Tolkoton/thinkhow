"""Helpers of the notes-readers catch-up tests of the smoke script (slice tester).

Written from the contract (.engine/slices/notes-readers.md, «Goal» (2) and «Exit criterion»), not from the
script. The script is run from the repository root through a small bootstrap that wraps the two public
functions the contract names: `thinkhow.facilitation.route.router_instruction` and
`thinkhow.facilitation.respond.system_instruction`. The wrappers call the real functions, record what they
were given and what they returned, and — when `NR_BREAK` names a breakage — damage exactly the one thing
«Goal» (2) says the smoke shows: the router note stands in the `pre-mortem` section and nowhere else; the
`facilitator` note is in the instruction of `five-whys` and not in the one of `pre-mortem`. A script that
shows a value has to exit non-zero when the value is wrong.

The artifact `.engine/artifacts/notes-readers/smoke.txt` is kept as it was: every run is wrapped by
`keep_artifact`, and the text the run wrote there is returned to the test.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "scripts" / "smoke_test_notes_readers.py"
ARTIFACT = REPO / ".engine" / "artifacts" / "notes-readers" / "smoke.txt"

BOOT = r"""
import json
import os
import runpy
import sys
from pathlib import Path

import importlib

import thinkhow.facilitation as F

# `thinkhow.facilitation` re-exports functions named like its modules: take the modules themselves
RS = importlib.import_module("thinkhow.facilitation.respond")
RT = importlib.import_module("thinkhow.facilitation.route")
from thinkhow.facilitation.route import CARDS_HEAD

SCRIPT = Path(sys.argv[1])
REC = Path(os.environ["NR_RECORD"])
BREAK = os.environ.get("NR_BREAK", "")
real_router = RT.router_instruction
real_system = RS.system_instruction
seen = {"router_calls": [], "system_calls": [], "broken": []}


def save():
    REC.write_text(json.dumps(seen, ensure_ascii=False, default=str), encoding="utf-8")


def one_line(text):
    return " ".join(text.split())


def recs(memory):
    return [{"id": r.id, "title": r.title, "cards": list(r.cards), "audience": r.audience} for r in memory]


def headers(text):
    # positions of the card sections «### <id> — » after CARDS_HEAD
    start = text.index(CARDS_HEAD)
    out = []
    pos = start
    while True:
        i = text.find("\n### ", pos)
        if i < 0:
            return out
        line_end = text.find("\n", i + 1)
        line = text[i + 1 : line_end if line_end >= 0 else len(text)]
        out.append((i + 1, line[4:].split(" — ")[0]))
        pos = i + 1


def router_instruction(knowledge, *args, **kwargs):
    text = real_router(knowledge, *args, **kwargs)
    notes = [r for r in knowledge.memory if r.audience == "router"]
    if notes and BREAK == "router_note_elsewhere":
        rec = notes[0]
        line = f"- {rec.title}. {one_line(rec.noticed)} {one_line(rec.do)}"
        hs = headers(text)
        idx = next(k for k, (_, cid) in enumerate(hs) if cid not in rec.cards)
        cut = hs[idx + 1][0] if idx + 1 < len(hs) else len(text)
        text = text[:cut].rstrip("\n") + f"\nДосвід:\n{line}\n\n" + text[cut:].lstrip("\n")
        seen["broken"].append(("router_note_elsewhere", hs[idx][1]))
    if notes and BREAK == "router_note_missing":
        kept = [ln for ln in text.split("\n") if not any(r.title in ln for r in notes)]
        text = "\n".join(ln for ln in kept if ln != "Досвід:")
        seen["broken"].append(("router_note_missing", ""))
    seen["router_calls"].append(
        {"cards": sorted(knowledge.cards), "memory": recs(knowledge.memory), "text": text}
    )
    save()
    return text


def system_instruction(card, memory, *args, **kwargs):
    text = real_system(card, memory, *args, **kwargs)
    mine = [r for r in memory if r.audience == "facilitator"]
    head = "# Пам'ять досвіду\n"
    if BREAK == "facilitator_note_missing" and any(card.id in r.cards for r in mine):
        text = text[: text.index(head) + len(head)] + "(поки порожня)\n"
        seen["broken"].append(("facilitator_note_missing", card.id))
    if BREAK == "facilitator_note_leaks" and mine and not any(card.id in r.cards for r in mine):
        other = card.model_copy(update={"id": mine[0].cards[0]})
        theirs = real_system(other, memory, *args, **kwargs)
        text = text[: text.index(head)] + theirs[theirs.index(head) :]
        seen["broken"].append(("facilitator_note_leaks", card.id))
    seen["system_calls"].append({"card": card.id, "memory": recs(memory), "text": text})
    save()
    return text


RT.router_instruction = router_instruction
RS.system_instruction = system_instruction
for name, fn in (("router_instruction", router_instruction), ("system_instruction", system_instruction)):
    if hasattr(F, name):
        setattr(F, name, fn)

save()
sys.path.insert(0, str(SCRIPT.parent))
sys.argv = [str(SCRIPT)]
runpy.run_path(str(SCRIPT), run_name="__main__")
"""


@contextmanager
def keep_artifact() -> Iterator[None]:
    """The repository's smoke.txt is the same after the test as before it."""
    before = ARTIFACT.read_bytes() if ARTIFACT.exists() else None
    try:
        yield
    finally:
        if before is None:
            ARTIFACT.unlink(missing_ok=True)
        else:
            ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
            ARTIFACT.write_bytes(before)


def real_card_ids() -> list[str]:
    """The `id` of every card file in `cards/` (the 25 real cards), read without the code under test."""
    ids = []
    for path in sorted((REPO / "cards").glob("*.yaml")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("id:"):
                ids.append(line[3:].strip().strip("'\""))
                break
    return sorted(ids)


def run_smoke(
    tmp: Path, breakage: str = ""
) -> tuple[subprocess.CompletedProcess[str], dict[str, Any], str | None]:
    """Run the smoke script from the repository root.

    Returns the run, what the wrappers recorded and the text of the artifact the run left (None: none).
    """
    tmp.mkdir(parents=True, exist_ok=True)
    boot = tmp / "nr_boot.py"
    boot.write_text(BOOT, encoding="utf-8")
    record = tmp / "nr_record.json"
    work = tmp / "work"
    work.mkdir(exist_ok=True)
    env = dict(
        os.environ,
        TMPDIR=str(work),
        TEMP=str(work),
        TMP=str(work),
        NR_RECORD=str(record),
        NR_BREAK=breakage,
    )
    env.pop("PYTHONSAFEPATH", None)
    env["PYTHONPATH"] = os.pathsep.join(filter(None, [str(REPO / "src"), os.environ.get("PYTHONPATH", "")]))
    with keep_artifact():
        ARTIFACT.unlink(missing_ok=True)
        result = subprocess.run(
            [sys.executable, str(boot), str(SCRIPT)],
            cwd=REPO,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=600,
        )
        artifact = ARTIFACT.read_text(encoding="utf-8") if ARTIFACT.exists() else None
    seen: dict[str, Any] = json.loads(record.read_text(encoding="utf-8")) if record.exists() else {}
    return result, seen, artifact
