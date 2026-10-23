"""The tracer bullet, locally (feature «Integration exit criterion»): local folder, scripted model.

Part 1 (skel-web): seed → create a topic → a turn → SSE → conversation.md + map.json; no button to close.
Part 2 (skel-learning, task 202): `analyze` takes the new turns at once, a repeat writes nothing, a new
turn is analyzed alone; each observation's link opens an existing turn (PR-09).
"""

import json
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from thinkhow.learning import job
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
    assert client.post("/language", data={"code": "uk-UA"}).status_code == 303  # F13: language first
    assert "Мої теми" in client.get("/").text
    topic = client.post("/topics", data={"title": "Кав'ярня"}).headers["location"]
    stream = client.post(f"{topic}/reply", data={"text": "Хочу відкрити кав'ярню за три місяці."})
    events = sse_events(stream.text)
    assert [name for name, _ in events][0] == "saved" and events[-1] == ("answered", {"turn": 2})
    assert client.post(f"{topic}/close").status_code == 404
    assert "Завершити сесію" not in client.get(topic).text
    folder = tmp_path / "users" / "local-owner" / topic.rsplit("/", 1)[-1]
    conversation = (folder / "conversation.md").read_text(encoding="utf-8")
    assert "<!-- thinkhow:turn 1 user" in conversation and "<!-- thinkhow:turn 2 model" in conversation
    assert "<!-- thinkhow:closed" not in conversation
    shown = "".join(str(data["text"]) for name, data in events if name == "delta")
    assert shown in conversation
    problem_map = json.loads((folder / "map.json").read_text(encoding="utf-8"))
    assert [item["id"] for item in problem_map["items"]] == ["i1"]
    assert (tmp_path / "system" / "knowledge" / "changes" / "000001.json").is_file()

    def analyze() -> dict[str, bytes]:
        assert job.run(["analyze"], environ, CARDS, lambda: datetime.now(UTC)) == 0
        return {f.name: f.read_bytes() for f in observations.iterdir()}

    topic_id = topic.rsplit("/", 1)[-1]
    observations = tmp_path / "system" / "learning" / "observations" / "local-owner" / topic_id
    first = analyze()
    assert set(first) == {"t1-t2.json"}
    assert analyze() == first
    stream = client.post(f"{topic}/reply", data={"text": "Перший крок — знайти приміщення."})
    assert sse_events(stream.text)[-1] == ("answered", {"turn": 4})
    third = analyze()
    assert set(third) == {"t1-t2.json", "t3-t4.json"} and third["t1-t2.json"] == first["t1-t2.json"]
    newest = json.loads(third["t3-t4.json"])
    assert (newest["first_turn"], newest["last_turn"]) == (3, 4) and newest["turn"] in (3, 4)
    page = client.get(topic).text
    for data in third.values():
        observation = json.loads(data)
        assert observation["link"] == f"{topic}#t{observation['turn']}"
        assert f'id="t{observation["turn"]}"' in page
