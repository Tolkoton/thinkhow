"""Manual smoke of thinkhow.platform: a local folder for storage, the real Gemini on Vertex AI (`eu`).

Run: `uv run python scripts/smoke_test_skel_platform.py` (needs Application Default Credentials).
"""

import importlib
import json
import os
import sys
import tempfile
from pathlib import Path

from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
platform = {
    name: importlib.import_module(f"thinkhow.platform.{name}") for name in ("config", "llm", "storage")
}


class Answer(BaseModel):
    reply: str
    phase: str


def check_storage() -> None:
    with tempfile.TemporaryDirectory() as root:
        storage = platform["storage"].LocalStorage(Path(root))
        storage.write("users", "u1/a.json", b"{}", "application/json")
        assert storage.read("users", "u1/a.json") == b"{}"
        assert storage.list("users", "u1/") == ["u1/a.json"]
        assert storage.create_if_absent("system", "k/1.json", b"1", "application/json") is True
        assert storage.create_if_absent("system", "k/1.json", b"2", "application/json") is False
        assert storage.read("system", "k/1.json") == b"1"
    print("LocalStorage write/read/list/create_if_absent OK")


def check_llm() -> None:
    environ = {**os.environ, "THINKHOW_LOCAL": "false"}
    for name in ("THINKHOW_USERS_BUCKET", "THINKHOW_SYSTEM_BUCKET", "THINKHOW_OWNER_EMAIL"):
        environ.setdefault(name, "smoke")
    llm_module = platform["llm"]
    llm = llm_module.make_llm(platform["config"].load_settings(environ), script=lambda *_: "")
    print("the llm_call log line (one JSON line, tokens, no text):")
    events = list(
        llm.stream_json(
            "Ти фасилітатор. Відповідай українською, двома-трьома реченнями; phase — 'intro'.",
            [llm_module.Turn("user", "Хочу перевірити план запуску курсу. З чого почати?")],
            Answer,
            llm_module.KnowledgeRev(1, 1),
        )
    )
    deltas = [e.text for e in events if isinstance(e, llm_module.ReplyDelta)]
    done = events[-1]
    assert isinstance(done, llm_module.Done)
    reply = json.loads(done.raw_json)["reply"]
    assert len(deltas) >= 2 and "".join(deltas) == reply, (len(deltas), reply)
    print(f"stream_json gave {len(deltas)} deltas; joined == reply OK")


if __name__ == "__main__":
    check_storage()
    check_llm()
