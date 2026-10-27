"""Smoke of slice spoken-replies: in-process app of local mode, the form's `spoken=1` reaches the model.

Run: `uv run python scripts/smoke_test_spoken_replies.py`. The app is built as `build_deps` builds it, with
`facilitate` assembled from the same `respond` and the scripted model wrapped by a recorder of each call's
system instruction (the wrapper lives here, not in src/). Asserts by itself; prints each step.
"""

import dataclasses
import functools
import sys
import tempfile
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import importlib  # noqa: E402 — thinkhow is reached through src/ on sys.path, as smoke_test_skel_learning does

SECTION = "# Людина слухає"


class Recording:
    """The scripted model with every system instruction it was given kept, in order."""

    def __init__(self, llm: Any) -> None:
        self.llm = llm
        self.systems: list[str] = []

    def stream_json(self, system: str, *args: Any, **kwargs: Any) -> Any:
        self.systems.append(system)
        return self.llm.stream_json(system, *args, **kwargs)

    def generate_json(self, system: str, *args: Any, **kwargs: Any) -> Any:
        self.systems.append(system)
        return self.llm.generate_json(system, *args, **kwargs)


def main() -> None:
    knowledge = importlib.import_module("thinkhow.knowledge")
    respond = importlib.import_module("thinkhow.facilitation").respond
    load_settings = importlib.import_module("thinkhow.platform.config").load_settings
    make_llm = importlib.import_module("thinkhow.platform.llm").make_llm
    app_module = importlib.import_module("thinkhow.web.app")
    server = importlib.import_module("thinkhow.web.server")
    local = importlib.import_module("thinkhow.web.local")
    env = {"THINKHOW_LOCAL": "true", "THINKHOW_LOCAL_DIR": tempfile.mkdtemp(prefix="thinkhow-spoken-")}
    env["THINKHOW_OWNER_EMAIL"] = "owner@localhost"
    deps = app_module.build_deps(env, ROOT / "cards")
    llm = make_llm(
        load_settings(env),
        local.local_script,
        search=True,
        found_script=local.local_found,
        search_script=local.local_search,
    )
    recording = Recording(llm)
    facilitate = functools.partial(respond, knowledge=knowledge.current(deps.storage), llm=recording)
    client = TestClient(
        server.create_app(dataclasses.replace(deps, facilitate=facilitate)), follow_redirects=False
    )
    assert client.post("/language", data={"code": "uk-UA"}).status_code == 303
    topic = client.post("/topics", data={"title": "Голос"}).headers["location"]
    for spoken, text in (("1", "Я думаю, чи переїжджати до Львова."), ("", "А що далі?")):
        before = len(recording.systems)
        fields = {"text": text, **({"spoken": spoken} if spoken else {})}
        response = client.post(topic + "/reply", data=fields)
        assert response.status_code == 200 and "event: answered" in response.text, response.text[-300:]
        systems = recording.systems[before:]
        with_section = [SECTION in s for s in systems]
        print(
            f"spoken={spoken or '—'}: 200 SSE answered; calls {len(systems)}, section in each: {with_section}"
        )
        assert systems and all(with_section) == (spoken == "1") and any(with_section) == (spoken == "1"), (
            with_section
        )
    print("OK: with spoken=1 every system instruction has «# Людина слухає», without it none has")


if __name__ == "__main__":
    main()
