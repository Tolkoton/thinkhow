"""Manual smoke of thinkhow.knowledge: seed the repository cards/ into a temporary local folder, read back.

Run: `uv run python scripts/smoke_test_skel_knowledge.py`. The real bucket is the owner's (Job `seed`, PR-07).
"""

import importlib
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
knowledge = importlib.import_module("thinkhow.knowledge")
storage_module = importlib.import_module("thinkhow.platform.storage")


def main() -> None:
    with tempfile.TemporaryDirectory() as root:
        storage = storage_module.LocalStorage(Path(root))
        first, second = knowledge.seed(storage, ROOT / "cards"), knowledge.seed(storage, ROOT / "cards")
        print(f"first seed: {first}; second seed: {second}")
        assert (first, second) == (True, False)
        state = knowledge.current(storage)
        print(f"rev {state.rev}, n {state.n}, cards {sorted(state.cards)}, memory {state.memory}")
        assert (state.rev, state.n, sorted(state.cards), state.memory) == (1, 0, ["pre-mortem"], [])
        print("--- card_prompt(pre-mortem) ---")
        print(knowledge.card_prompt(state.cards["pre-mortem"]))
    print("Look: the card above is Ukrainian and has 4 phases, each with its id and «Вихід».")


if __name__ == "__main__":
    main()
