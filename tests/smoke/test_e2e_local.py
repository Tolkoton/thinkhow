"""The tracer bullet, locally (feature «Integration exit criterion»): local folder, scripted model.

Part 1 (skel-web): seed → create a topic → a turn → SSE → conversation.md + map.json → close the session.
"""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from thinkhow.web.app import build_deps
from thinkhow.web.server import create_app

CARDS = Path(__file__).resolve().parents[2] / "cards"


def sse_events(body: str) -> list[tuple[str, dict[str, object]]]:
    events = []
    for block in body.strip().split("\n\n"):
        name, data = block.split("\n")
        events.append((name.removeprefix("event: "), json.loads(data.removeprefix("data: "))))
    return events


def test_local_chain_from_a_new_topic_to_the_files(tmp_path: Path) -> None:
    environ = {
        "THINKHOW_LOCAL": "true",
        "THINKHOW_LOCAL_DIR": str(tmp_path),
        "THINKHOW_OWNER_EMAIL": "owner@localhost",
    }
    client = TestClient(create_app(build_deps(environ, CARDS)), follow_redirects=False)
    assert "Мої теми" in client.get("/").text
    topic = client.post("/topics", data={"title": "Кав'ярня"}).headers["location"]
    stream = client.post(f"{topic}/reply", data={"text": "Хочу відкрити кав'ярню за три місяці."})
    events = sse_events(stream.text)
    assert [name for name, _ in events][0] == "saved" and events[-1] == ("answered", {"turn": 2})
    assert client.post(f"{topic}/close").status_code == 303
    folder = tmp_path / "users" / "local-owner" / topic.rsplit("/", 1)[-1]
    conversation = (folder / "conversation.md").read_text(encoding="utf-8")
    assert "<!-- thinkhow:turn 1 user" in conversation and "<!-- thinkhow:turn 2 model" in conversation
    assert "<!-- thinkhow:closed 1" in conversation
    shown = "".join(str(data["text"]) for name, data in events if name == "delta")
    assert shown in conversation
    problem_map = json.loads((folder / "map.json").read_text(encoding="utf-8"))
    assert [item["id"] for item in problem_map["items"]] == ["i1"]
    assert (tmp_path / "system" / "knowledge" / "changes" / "000001.json").is_file()
