"""Smoke of slice knowledge-versions: the real 25 cards, a memory change, a rollback (learning-loop S1).

Run: `uv run python scripts/smoke_test_knowledge_versions.py`. A temporary local folder; `seed` from cards/,
`apply_memory` with a scripted person-details check and the real `measure`, then `rollback`. Prints each step
and writes the same to .engine/artifacts/knowledge-versions/smoke.txt; exits 1 on any failed check.
"""

import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from thinkhow.knowledge import MemoryChange, MemoryRecord, apply_memory, changes, current, rollback, seed  # noqa: E402
from thinkhow.learning.vet import measure  # noqa: E402
from thinkhow.platform.storage import LocalStorage  # noqa: E402

OUT = ROOT / ".engine" / "artifacts" / "knowledge-versions" / "smoke.txt"
NOTE = MemoryRecord(
    id="pre-mortem-facilitator",
    title="Коли «не знаю, що може піти не так»",
    cards=["pre-mortem"],
    noticed="Людина не може уявити провалу власного плану.",
    do="Запропонуй уявити, що минув рік і план провалився, і спитати, яка новина про це була б першою.",
    basis="смоук slice-а knowledge-versions",
    audience="facilitator",
)


def cards_bytes(root: Path) -> dict[str, bytes]:
    base = root / "system" / "knowledge" / "cards"
    return {p.relative_to(base).as_posix(): p.read_bytes() for p in sorted(base.rglob("*.json"))}


def main() -> int:
    lines: list[str] = []
    ok = True

    def say(text: str) -> None:
        print(text)
        lines.append(text)

    def check(condition: bool, text: str) -> None:
        nonlocal ok
        ok = ok and condition
        say(f"{'OK  ' if condition else 'FAIL'} {text}")

    root = Path(tempfile.mkdtemp(prefix="thinkhow-kv-"))
    storage = LocalStorage(root)
    seed(storage, ROOT / "cards")
    before = cards_bytes(root)
    start = current(storage)
    say(
        f"seed: rev {start.rev}, cards {len(start.cards)}, memory {len(start.memory)}, "
        f"measure {measure(start)}"
    )
    change = MemoryChange(what="смоук: одна нотатка", why="перевірка", by="smoke", upsert=[NOTE], remove=[])
    rev = apply_memory(storage, change, lambda records: None, measure)
    after = current(storage)
    say(f"apply_memory: rev {rev}; memory {[m.id for m in after.memory]}; n {after.n}")
    check(rev == start.rev + 1, "a new revision")
    check([m.id for m in after.memory] == [NOTE.id], "the note is in current().memory")
    n = rollback(storage, rev or 0, "smoke@localhost", datetime.now(UTC))
    rolled = current(storage)
    say(f"rollback: n {n}; memory {[m.id for m in rolled.memory]}; rev_pair {rolled.rev_pair()}")
    check(rolled.memory == [] and rolled.n == 1, "the note is gone, n = 1")
    check(cards_bytes(root) == before, "the card files are byte-for-byte the same")
    feed = changes(storage)
    say("feed: " + "; ".join(f"rev {v.rev} {v.what!r} rolled_back={v.rolled_back}" for v in feed))
    check(feed[0].rolled_back == 1 and feed[0].rollback_changed == [NOTE.id], "the feed shows the rollback")
    say("RESULT: " + ("PASS" if ok else "FAIL"))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
