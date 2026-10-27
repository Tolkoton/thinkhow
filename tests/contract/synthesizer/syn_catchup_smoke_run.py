"""Helpers of the synthesizer catch-up tests of the smoke script (slice tester).

Written from the contract (.engine/slices/synthesizer.md, «Goal» (2), «Hardest seams» Seam 5 and «Exit
criterion»), not from the script. The script is run from the repository root through a small bootstrap that
wraps the public names the tracer goes through: `analyze` and `synthesize` as the Job calls them
(`thinkhow.learning.job`), and `thinkhow.knowledge.rollback` as the web route calls it. The wrappers call the
real functions, record what happened, and — when `SYN_BREAK` names a breakage — damage exactly one value the
contract says the smoke checks. A script that "checks" a value has to exit non-zero when the value is wrong.

The artifact `.engine/artifacts/synthesizer/smoke.txt` is kept as it was: every run is wrapped by
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
SCRIPT = REPO / "scripts" / "smoke_test_learning_loop.py"
ARTIFACT = REPO / ".engine" / "artifacts" / "synthesizer" / "smoke.txt"

BOOT = r"""
import json
import os
import runpy
import sys
from pathlib import Path

import thinkhow.knowledge as K
import thinkhow.knowledge.versions as V
import thinkhow.learning.job as J
from thinkhow.knowledge import MemoryChange, MemoryRecord, current
from thinkhow.learning.synthesize import SynthesisReport, SynthesisRun, runs
from thinkhow.platform.storage import LocalStorage

SCRIPT = Path(sys.argv[1])
REC = Path(os.environ["SYN_RECORD"])
BREAK = os.environ.get("SYN_BREAK", "")
real_analyze = J.analyze
real_synthesize = J.synthesize
real_rollback = K.rollback
seen = {"analyze_calls": 0, "synthesize_calls": 0, "rollback_calls": 0, "reports": [], "writes": []}


def save():
    REC.write_text(json.dumps(seen, ensure_ascii=False, default=str), encoding="utf-8")


def passing_vet(records):
    return None


def zero_measure(knowledge):
    return 0


def files(storage, prefix):
    return sorted(storage.list("system", prefix))


def analyze(*args, **kwargs):
    seen["analyze_calls"] += 1
    result = real_analyze(*args, **kwargs)
    storage = args[0] if args else kwargs["storage"]
    if BREAK == "link_elsewhere":
        for path in files(storage, "learning/observations/"):
            data = json.loads(storage.read("system", path))
            for obs in data.get("observations", []):
                obs["link"] = "/elsewhere"
            storage.write("system", path, json.dumps(data, ensure_ascii=False).encode(), "application/json")
            seen["link_broken"] = True
    save()
    return result


def synthesize(storage, llm, now, vet, measure):
    seen["synthesize_calls"] += 1
    call = seen["synthesize_calls"]
    seen["local"] = isinstance(storage, LocalStorage)
    before = {"runs": files(storage, "learning/synthesis/"), "changes": len(K.changes(storage))}
    if BREAK == "first_nothing" and call == 1:
        report = SynthesisReport(rev=None, considered=0, outcome="nothing_new")
    elif BREAK == "second_failed" and call == 2:
        report = SynthesisReport(rev=None, considered=0, outcome="failed")
    else:
        report = real_synthesize(storage, llm, now, vet, measure)
    if call == 1 and report.outcome == "applied":
        seen["first_notes"] = [r.model_dump(mode="json") for r in current(storage).memory]
    if BREAK == "card_bytes" and call == 1:
        paths = files(storage, "knowledge/cards/")
        data = storage.read("system", paths[0])
        storage.write("system", paths[0], data + b"\n", "application/json")
        seen["card_touched"] = paths[0]
    if BREAK == "second_run_record" and call == 2:
        done = runs(storage)
        refed = SynthesisRun(
            at=now, considered=list(done[0].considered), outcome="rejected", rev=None, rejected="break"
        )
        path = f"learning/synthesis/{now:%Y%m%dT%H%M%SZ}-9.json"
        seen["extra_run"] = storage.create_if_absent(
            "system", path, refed.model_dump_json().encode(), "application/json"
        )
    if BREAK == "second_revision" and call == 2:
        cards = sorted(current(storage).cards)
        note = MemoryRecord(
            id="break-note", title="break", cards=[cards[0]], noticed="break", do="break", basis="break",
            audience="facilitator",
        )
        change = MemoryChange(what="break", why="break", by="synthesizer", upsert=[note], remove=[])
        seen["extra_rev"] = K.apply_memory(storage, change, passing_vet, zero_measure)
    after = {"runs": files(storage, "learning/synthesis/"), "changes": len(K.changes(storage))}
    seen["reports"].append({"outcome": report.outcome, "rev": report.rev, "considered": report.considered})
    seen["writes"].append({"before": before, "after": after})
    save()
    return report


def rollback(storage, rev, by, now):
    seen["rollback_calls"] += 1
    notes = list(current(storage).memory)
    n = real_rollback(storage, rev, by, now)
    seen["memory_after_real_rollback"] = [r.id for r in current(storage).memory]
    if BREAK == "rollback_keeps" and notes:
        change = MemoryChange(what="break", why="break", by="break", upsert=notes, remove=[])
        seen["re_applied"] = K.apply_memory(storage, change, passing_vet, zero_measure)
    save()
    return n


J.analyze = analyze
J.synthesize = synthesize
for module in (K, V):
    module.rollback = rollback

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


def run_smoke(
    tmp: Path, breakage: str = ""
) -> tuple[subprocess.CompletedProcess[str], dict[str, Any], str | None]:
    """Run the smoke script from the repository root.

    Returns the run, what the wrappers recorded and the text of the artifact the run left (None: none).
    """
    tmp.mkdir(parents=True, exist_ok=True)
    boot = tmp / "syn_boot.py"
    boot.write_text(BOOT, encoding="utf-8")
    record = tmp / "syn_record.json"
    work = tmp / "work"
    work.mkdir(exist_ok=True)
    env = dict(
        os.environ,
        TMPDIR=str(work),
        TEMP=str(work),
        TMP=str(work),
        SYN_RECORD=str(record),
        SYN_BREAK=breakage,
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
