"""Composition root of the Cloud Run Job: `python -m thinkhow.learning.job seed|cards|analyze|synthesize`.

A failed session is not a failed Job (Q3): it is in the log, and the next run tries it again.
"""

import os
import sys
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path

from thinkhow import knowledge
from thinkhow.learning.analyze import analyze
from thinkhow.learning.local import local_script
from thinkhow.learning.synthesize import synthesize
from thinkhow.learning.vet import measure, vet_with
from thinkhow.platform.config import load_settings
from thinkhow.platform.llm import make_llm
from thinkhow.platform.log import log_event
from thinkhow.platform.storage import make_storage

CARDS_DIR = Path(__file__).resolve().parents[3] / "cards"
USAGE = "usage: python -m thinkhow.learning.job seed|cards|analyze|synthesize"


def run(argv: Sequence[str], environ: Mapping[str, str], cards_dir: Path, now: Callable[[], datetime]) -> int:
    command = argv[0] if argv else ""
    if command not in ("seed", "cards", "analyze", "synthesize"):
        print(USAGE, file=sys.stderr)
        return 2
    settings = load_settings(environ)
    storage = make_storage(settings)
    if command == "seed":
        log_event("seed_done", created=knowledge.seed(storage, cards_dir))
    elif command == "cards":
        log_event("cards_published", rev=knowledge.publish(storage, cards_dir))
    elif command == "analyze":
        analyze(storage, make_llm(settings, local_script), now())
    else:
        llm = make_llm(settings, local_script)
        synthesize(storage, llm, now(), vet_with(llm), measure)
    return 0


if __name__ == "__main__":
    sys.exit(run(sys.argv[1:], os.environ, CARDS_DIR, lambda: datetime.now(UTC)))
