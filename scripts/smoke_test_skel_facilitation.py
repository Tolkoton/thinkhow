"""Manual smoke of thinkhow.facilitation: one reply by the Pre-mortem card on the real Gemini (Vertex, `eu`).

Run: `uv run python scripts/smoke_test_skel_facilitation.py` (needs Application Default Credentials).
"""

import importlib
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
facilitation = importlib.import_module("thinkhow.facilitation")
knowledge_module = importlib.import_module("thinkhow.knowledge")
config = importlib.import_module("thinkhow.platform.config")
llm_module = importlib.import_module("thinkhow.platform.llm")
storage_module = importlib.import_module("thinkhow.platform.storage")

TEXT = "Хочу за три місяці відкрити кав'ярню з обсмажуванням у Львові. Перевірмо план, поки не пізно."


def main() -> None:
    with tempfile.TemporaryDirectory() as root:
        storage = storage_module.LocalStorage(Path(root))
        knowledge_module.seed(storage, ROOT / "cards")
        knowledge = knowledge_module.current(storage)
    environ = {**os.environ, "THINKHOW_LOCAL": "false"}
    for name in ("THINKHOW_USERS_BUCKET", "THINKHOW_SYSTEM_BUCKET", "THINKHOW_OWNER_EMAIL"):
        environ.setdefault(name, "smoke")
    llm = llm_module.make_llm(config.load_settings(environ), script=lambda *_: "")
    ctx = facilitation.FacilitationContext(
        card_id="pre-mortem", history=[], problem_map=facilitation.ProblemMap(), turn_no=1, text=TEXT
    )
    items = list(facilitation.respond(ctx, knowledge, llm))
    deltas = [i.text for i in items if isinstance(i, facilitation.ReplyDelta)]
    update = items[-1]
    phases = {p.id for p in knowledge.cards["pre-mortem"].facilitator.phases}
    print("person:", TEXT)
    print("facilitator:", update.reply)
    print(f"question marks in the reply (for information, as in PoC 101): {update.reply.count('?')}")
    print(f"deltas: {len(deltas)}; phase: {update.current_phase_id}; exit met: {update.phase_exit_met}")
    for change in update.map_updates:
        print(f"  map {change.op} {change.id} [{change.type}] {change.text} ({change.turn})")
    assert isinstance(update, facilitation.FacilitatorUpdate)
    assert len(deltas) >= 2, "the reply did not stream"
    assert "".join(deltas) == update.reply
    assert update.current_phase_id in phases
    print("OK: streamed, joined deltas == reply, the phase is the card's")


if __name__ == "__main__":
    main()
