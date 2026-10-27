"""Composition root of the Cloud Run Job: `python -m thinkhow.learning.job seed|cards|analyze|synthesize`.

A failed session is not a failed Job (Q3): it is in the log, and the next run tries it again.
"""

import os
import sys
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from thinkhow import knowledge
from thinkhow.learning.analyze import analyze
from thinkhow.learning.local import local_script
from thinkhow.learning.synthesize import synthesize
from thinkhow.learning.vet import measure, vet_with
from thinkhow.platform.config import load_settings
from thinkhow.platform.llm import Llm, LlmUnavailable, make_llm
from thinkhow.platform.log import log_event
from thinkhow.platform.storage import Storage, make_storage

CARDS_DIR = Path(__file__).resolve().parents[3] / "cards"
NOTES_DIR = Path(__file__).resolve().parents[3] / "notes"
USAGE = "usage: python -m thinkhow.learning.job seed|cards|analyze|synthesize|notes"


def run(argv: Sequence[str], environ: Mapping[str, str], cards_dir: Path, now: Callable[[], datetime]) -> int:
    command = argv[0] if argv else ""
    if command not in ("seed", "cards", "notes", "analyze", "synthesize"):
        print(USAGE, file=sys.stderr)
        return 2
    settings = load_settings(environ)
    storage = make_storage(settings)
    if command == "seed":
        log_event("seed_done", created=knowledge.seed(storage, cards_dir))
    elif command == "cards":
        log_event("cards_published", rev=knowledge.publish(storage, cards_dir))
    elif command == "notes":
        return _notes(storage, make_llm(settings, local_script))
    elif command == "analyze":
        analyze(storage, make_llm(settings, local_script), now())
    else:
        llm = make_llm(settings, local_script)
        synthesize(storage, llm, now(), vet_with(llm), measure)
    return 0


def _notes(storage: Storage, llm: Llm) -> int:
    """Flow: the repository's notes → those no `notes` change ever upserted and no other writer holds → one
    revision through the version check (learning-loop S5: what `notes` once published, or was rolled back or
    removed, does not come back; what the synthesizer holds is not overwritten)."""
    published = {r.id for view in knowledge.changes(storage) if view.by == "notes" for r in view.upserted}
    held = {r.id for r in knowledge.current(storage).memory}
    new = [r for r in knowledge.read_notes(NOTES_DIR) if r.id not in published | held]
    if not new:
        log_event("notes_published", rev=None, count=0)
        return 0
    change = knowledge.MemoryChange(
        what=f"стартові нотатки до методів: {len(new)}",
        why="дослідження типових випадків застосування (задача 309)",
        by="notes",
        upsert=new,
        remove=[],
    )
    try:
        rev = knowledge.apply_memory(storage, change, vet_with(llm), measure)
    except knowledge.VersionRejected as refused:
        log_event("notes_rejected", severity="WARNING", reason=refused.reason)
        return 1
    except (LlmUnavailable, ValidationError) as exc:
        log_event("notes_failed", severity="WARNING", error=type(exc).__name__)
        return 1
    log_event("notes_published", rev=rev, count=len(new) if rev is not None else 0)
    return 0


if __name__ == "__main__":
    sys.exit(run(sys.argv[1:], os.environ, CARDS_DIR, lambda: datetime.now(UTC)))
