"""Smoke of the learning loop, locally (feature learning-loop, the tracer S1 → S2 → S3; slice synthesizer).

Run: `uv run python scripts/smoke_test_learning_loop.py`. A temporary local folder, the scripted model of
local mode, the real app and the real Job: turns in a topic → `analyze` → `synthesize` → a new revision with
memory only → `/learning` shows the change with a link into the conversation → «Відкотити» →
`current().memory` without the note, the page says it was rolled back; a second `synthesize` takes nothing;
the card files byte-for-byte the same. Prints each step and writes the same to
.engine/artifacts/synthesizer/smoke.txt; exits 1 on a failed check.
"""

import re
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fastapi.testclient import TestClient  # noqa: E402

from thinkhow import knowledge  # noqa: E402
from thinkhow.learning import job  # noqa: E402
from thinkhow.learning.synthesize import runs  # noqa: E402
from thinkhow.platform.config import load_settings  # noqa: E402
from thinkhow.platform.storage import make_storage  # noqa: E402
from thinkhow.web.app import build_deps  # noqa: E402
from thinkhow.web.server import create_app  # noqa: E402

CARDS = ROOT / "cards"
OUT = ROOT / ".engine" / "artifacts" / "synthesizer" / "smoke.txt"


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

    root = Path(tempfile.mkdtemp(prefix="thinkhow-loop-"))
    environ = {
        "THINKHOW_LOCAL": "true",
        "THINKHOW_LOCAL_DIR": str(root),
        "THINKHOW_OWNER_EMAIL": "owner@localhost",
    }
    client = TestClient(create_app(build_deps(environ, CARDS)), follow_redirects=False)
    storage = make_storage(load_settings(environ))
    client.post("/language", data={"code": "uk-UA"})
    topic = client.post("/topics", data={"title": "Кав'ярня"}).headers["location"]
    client.post(f"{topic}/reply", data={"text": "Хочу відкрити кав'ярню за три місяці."})
    before = cards_bytes(root)
    rev_before = knowledge.current(storage).rev

    def run(command: str) -> int:
        return job.run([command], environ, CARDS, lambda: datetime.now(UTC))

    check(run("analyze") == 0, "analyze ran")
    check(run("synthesize") == 0, "synthesize ran")
    after = knowledge.current(storage)
    say(f"revision {rev_before} → {after.rev}; memory {[m.id for m in after.memory]}")
    check(after.rev == rev_before + 1 and len(after.memory) == 1, "a new revision with one note")
    feed = knowledge.changes(storage)
    newest = feed[0]
    check(
        newest.by == "synthesizer" and newest.observations != [],
        "the change is the synthesizer's and cites observations",
    )
    page = client.get("/learning").text
    links = re.findall(r'href="(/topics/[^"#]+#t\d+)"', page)
    say(f"/learning: {len(links)} links into conversations; button {'Відкотити' in page}")
    check(
        bool(links) and "Відкотити" in page, "the page shows the change, its observation links and the button"
    )
    turn = links[0].rsplit("#", 1)[-1]
    check(f'id="{turn}"' in client.get(links[0].split("#")[0]).text, f"the link opens the turn {turn}")
    answer = client.post(f"/learning/rollback/{newest.rev}")
    check(answer.status_code == 303, f"rollback over HTTP → {answer.status_code}")
    rolled = knowledge.current(storage)
    say(f"after rollback: memory {[m.id for m in rolled.memory]}; rev_pair {rolled.rev_pair()}")
    check(rolled.memory == [] and rolled.n == 1, "the note is gone, n = 1")
    check("відкочено (відкат 1)" in client.get("/learning").text, "the page says the change was rolled back")
    rev_now = knowledge.current(storage).rev_pair()
    check(run("synthesize") == 0, "a second synthesize ran")
    check(len(runs(storage)) == 1, "the second synthesize took nothing new (no second run record)")
    check(knowledge.current(storage).rev_pair() == rev_now, "and wrote no revision")
    check(cards_bytes(root) == before, "the card files are byte-for-byte the same")
    say("RESULT: " + ("PASS" if ok else "FAIL"))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
