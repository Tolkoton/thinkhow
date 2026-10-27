"""The app of the live conversation-mode check (task 308): local storage and local mode's fixed person, but
the real models — Gemini on Vertex `eu` with search, `gemini-3.5-transcribe`, Cloud TTS `eu`.

Run by `scripts/live_conversation_mode.py` as `uvicorn scripts.live_app:app` with THINKHOW_LOCAL=true and
THINKHOW_LOCAL_DIR set. Not for deployment: the fixed person makes everyone one person.
"""

import functools
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from thinkhow import knowledge  # noqa: E402
from thinkhow.facilitation import respond  # noqa: E402
from thinkhow.platform.config import load_settings  # noqa: E402
from thinkhow.platform.identity import make_identity  # noqa: E402
from thinkhow.platform.llm import make_llm  # noqa: E402
from thinkhow.platform.speech import make_speech  # noqa: E402
from thinkhow.platform.storage import make_storage  # noqa: E402
from thinkhow.platform.tts import make_tts  # noqa: E402
from thinkhow.web.server import Deps, create_app  # noqa: E402


def _build() -> Deps:
    settings = load_settings(os.environ)
    real = settings.model_copy(update={"local": False})
    storage = make_storage(settings)
    knowledge.seed(storage, ROOT / "cards")
    current = knowledge.current(storage)
    llm = make_llm(real, lambda *_: "", search=True)
    facilitate = functools.partial(respond, knowledge=current, llm=llm)
    now = lambda: datetime.now(UTC)  # noqa: E731
    return Deps(
        storage,
        make_identity(settings),
        settings,
        facilitate,
        now,
        make_speech(real),
        make_tts(real),
        current.cards,
    )


app = create_app(_build())
