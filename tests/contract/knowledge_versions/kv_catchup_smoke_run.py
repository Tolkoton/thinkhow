"""Helpers of the knowledge-versions catch-up tests of the smoke script (slice tester).

Written from the contract (.engine/slices/knowledge-versions.md, «Goal» (2) and «Exit criterion»),
not from the script. The script is run from the repository root, as the exit criterion names it,
through a small bootstrap that wraps the public `apply_memory` and `rollback` of `thinkhow.knowledge`:
the wrappers call the real functions, record what the script handed them, and — when `KV_BREAK` names
a breakage — damage the state the way the contract says the script must notice. A script that
"checks" a value has to fail when the value is wrong.

The artifact `.engine/artifacts/knowledge-versions/smoke.txt` is kept as it was: every run is wrapped
by `keep_artifact`.
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
SCRIPT = REPO / "scripts" / "smoke_test_knowledge_versions.py"
ARTIFACT = REPO / ".engine" / "artifacts" / "knowledge-versions" / "smoke.txt"

BOOT = r"""
import json
import os
import runpy
import sys
from pathlib import Path

import thinkhow.knowledge as K
import thinkhow.knowledge.versions as V
from thinkhow.knowledge import MemoryChange, current
from thinkhow.learning import vet as LV
from thinkhow.platform.storage import LocalStorage

SCRIPT = Path(sys.argv[1])
REC = Path(os.environ["KV_RECORD"])
BREAK = os.environ.get("KV_BREAK", "")
real_apply = K.apply_memory
real_rollback = K.rollback
seen = {"apply_calls": 0, "rollback_calls": 0}


def save():
    REC.write_text(json.dumps(seen, ensure_ascii=False), encoding="utf-8")


def passing_vet(records):
    return None


def zero_measure(knowledge):
    return 0


def apply_memory(storage, change, vet, measure):
    before = current(storage)
    seen["apply_calls"] += 1
    seen["local"] = isinstance(storage, LocalStorage)
    seen["cards_before_change"] = len(before.cards)
    seen["measure_is_real"] = measure(before) == LV.measure(before)
    seen["change"] = change.model_dump(mode="json")
    rev = real_apply(storage, change, vet, measure)
    seen["rev"] = rev
    if BREAK == "card_bytes":
        paths = storage.list("system", "knowledge/cards/")
        data = storage.read("system", paths[0])
        storage.write("system", paths[0], data + b"\n", "application/json")
        seen["card_touched"] = paths[0]
    if BREAK == "record_removed" and change.upsert:
        removed = real_apply(
            storage,
            MemoryChange(
                what="break", why="break", by="break", upsert=[], remove=[r.id for r in change.upsert]
            ),
            passing_vet,
            zero_measure,
        )
        seen["removed_by"] = removed
    save()
    return rev


def rollback(storage, rev, by, now):
    seen["rollback_calls"] += 1
    n = real_rollback(storage, rev, by, now)
    if BREAK == "record_back":
        again = real_apply(storage, MemoryChange(**seen["change"]), passing_vet, zero_measure)
        seen["re_applied"] = again
    if BREAK == "second_rollback":
        data = json.loads(storage.read("system", f"knowledge/rollbacks/{n:06d}.json"))
        data["n"] = n + 1
        data["changed"] = []
        seen["second"] = storage.create_if_absent(
            "system", f"knowledge/rollbacks/{n + 1:06d}.json", json.dumps(data).encode(), "application/json"
        )
    seen["n_after"] = current(storage).n
    save()
    return n


for module in (K, V):
    module.apply_memory = apply_memory
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


def run_smoke(tmp: Path, breakage: str = "") -> tuple[subprocess.CompletedProcess[str], dict[str, Any]]:
    """Run the smoke script from the repository root; return the run and what the wrappers recorded."""
    tmp.mkdir(parents=True, exist_ok=True)
    boot = tmp / "kv_boot.py"
    boot.write_text(BOOT, encoding="utf-8")
    record = tmp / "kv_record.json"
    work = tmp / "work"
    work.mkdir(exist_ok=True)
    env = dict(
        os.environ, TMPDIR=str(work), TEMP=str(work), TMP=str(work), KV_RECORD=str(record), KV_BREAK=breakage
    )
    env.pop("PYTHONSAFEPATH", None)
    env["PYTHONPATH"] = os.pathsep.join(filter(None, [str(REPO / "src"), os.environ.get("PYTHONPATH", "")]))
    result = subprocess.run(
        [sys.executable, str(boot), str(SCRIPT)],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=600,
    )
    seen: dict[str, Any] = json.loads(record.read_text(encoding="utf-8")) if record.exists() else {}
    return result, seen
