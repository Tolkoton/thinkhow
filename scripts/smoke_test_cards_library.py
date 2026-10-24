"""Manual smoke of cards-library: revision 1 with only Pre-mortem → the Job `cards` as a process → 18 cards.

Run: `uv run python scripts/smoke_test_cards_library.py`. Local storage in a temp folder; the real Job is the
owner's deployment (task 302, the request to Сонько). Revision 1 is seeded in this process from a copy folder
with only pre-mortem.yaml, because the Job process always seeds from the repository's cards/.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def job(command: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    run = [sys.executable, "-m", "thinkhow.learning.job", command]
    return subprocess.run(run, cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)


def published(result: subprocess.CompletedProcess[str]) -> object:
    lines = [json.loads(line) for line in result.stdout.splitlines() if line.startswith("{")]
    return next(line["rev"] for line in lines if line.get("event") == "cards_published")


def files(root: Path) -> list[str]:
    return sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file())


def main() -> None:
    from thinkhow import knowledge
    from thinkhow.platform.storage import LocalStorage

    data = Path(tempfile.mkdtemp(prefix="thinkhow-cards-"))
    only = Path(tempfile.mkdtemp(prefix="thinkhow-cards-one-"))
    shutil.copy(ROOT / "cards" / "pre-mortem.yaml", only / "pre-mortem.yaml")
    storage = LocalStorage(data)
    assert knowledge.seed(storage, only) is True
    first = knowledge.current(storage)
    print(f"seeded in process: rev {first.rev}, cards {sorted(first.cards)}")
    assert (first.rev, sorted(first.cards)) == (1, ["pre-mortem"])
    env = {
        **os.environ,
        "PYTHONPATH": str(ROOT / "src"),
        "THINKHOW_LOCAL": "true",
        "THINKHOW_LOCAL_DIR": str(data),
    }
    run = job("cards", env)
    print("job cards:", run.returncode, run.stdout.strip())
    assert run.returncode == 0 and published(run) == 2
    state = knowledge.current(storage)
    record = json.loads((data / "system" / "knowledge" / "changes" / "000002.json").read_text("utf-8"))
    print(f"rev {state.rev}, {len(state.cards)} cards: {sorted(state.cards)}")
    print(f"pre-mortem path: {record['cards']['pre-mortem']}")
    print(f"what: {record['what']}")
    assert state.rev == 2 and len(state.cards) == 18
    assert record["cards"]["pre-mortem"] == "knowledge/cards/pre-mortem/v1.json"
    for card_id, card in sorted(state.cards.items()):
        print(
            f"card_prompt({card_id}): {len(knowledge.card_prompt(card))} chars, "
            f"{len(card.facilitator.phases)} phases"
        )
    before = files(data)
    again = job("cards", env)
    print("job cards again:", again.returncode, again.stdout.strip())
    assert again.returncode == 0 and published(again) is None and files(data) == before
    print("OK: rev 1 (one card) → Job cards → rev 2 with 18 cards, Pre-mortem v1; a repeat writes nothing.")


if __name__ == "__main__":
    main()
