"""Contract tests of skel-web: local_script, build_deps in local mode end to end, a real uvicorn start."""

import http.client
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any, Literal

from pydantic import create_model
from skelweb_fakes import CARDS, REPO, sse_events

from thinkhow.facilitation.respond import answer_schema, update_schema
from thinkhow.facilitation.types import FacilitatorUpdate
from thinkhow.knowledge import current, seed
from thinkhow.platform.llm import Turn
from thinkhow.platform.storage import LocalStorage
from thinkhow.web.local import local_script

LOCAL_REPLY = "(локальний режим) Уявіть, що план провалився. Що сталося першим?"
PERSON = "Відкрию кав'ярню біля університету."
CONTENTS = [
    Turn("user", "Раніше"),
    Turn("model", "Розкажіть більше."),
    Turn(
        "user",
        f'[Карта проблеми зараз]\n{{"items":[],"phase_id":null,"last_turn":2}}\n\n'
        f"[Репліка людини #3]\n{PERSON}",
    ),
]


def card(tmp_path: Path) -> Any:
    store = LocalStorage(tmp_path / "k")
    seed(store, CARDS)
    return current(store).cards["pre-mortem"]


def _without_text(obj: dict[str, Any]) -> dict[str, Any]:
    return {**obj, "map_updates": [{k: v for k, v in u.items() if k != "text"} for u in obj["map_updates"]]}


def test_local_script_answer_schema_reply_first_first_phase_one_add(tmp_path: Path) -> None:
    schema = answer_schema(card(tmp_path))
    raw = local_script("system", CONTENTS, schema)
    obj = json.loads(raw)
    assert list(obj)[0] == "reply"
    assert _without_text(obj) == {
        "reply": LOCAL_REPLY,
        "current_phase_id": "phase_1_time_travel",
        "phase_exit_met": False,
        "map_updates": [{"op": "add", "id": "i3", "type": "plan", "turn": "t3"}],
    }
    assert PERSON in obj["map_updates"][0]["text"]
    schema.model_validate_json(raw)

    zeta_phases: Any = Literal["zeta", "alpha"]
    zeta = create_model("Z", __base__=FacilitatorUpdate, current_phase_id=(zeta_phases, ...))
    raw_z = local_script("system", [Turn("user", "[Репліка людини #11]\nТак")], zeta)
    obj_z = json.loads(raw_z)
    assert list(obj_z)[0] == "reply"
    assert obj_z["current_phase_id"] == "zeta"
    assert _without_text(obj_z)["map_updates"] == [{"op": "add", "id": "i11", "type": "plan", "turn": "t11"}]
    zeta.model_validate_json(raw_z)


def test_local_script_schema_without_reply_gives_the_same_without_reply(tmp_path: Path) -> None:
    schema = update_schema(card(tmp_path))
    raw = local_script("system", CONTENTS, schema)
    obj = json.loads(raw)
    assert "reply" not in obj
    assert _without_text(obj) == {
        "current_phase_id": "phase_1_time_travel",
        "phase_exit_met": False,
        "map_updates": [{"op": "add", "id": "i3", "type": "plan", "turn": "t3"}],
    }
    assert PERSON in obj["map_updates"][0]["text"]
    schema.model_validate_json(raw)


def local_env(tmp_path: Path) -> dict[str, str]:
    return {
        "THINKHOW_LOCAL": "true",
        "THINKHOW_LOCAL_DIR": str(tmp_path / "local"),
        "THINKHOW_OWNER_EMAIL": "owner@localhost",
    }


def test_e2e_local_mode_build_deps_topic_reply_close_files(tmp_path: Path) -> None:
    from fastapi.testclient import TestClient

    from thinkhow.web.app import build_deps
    from thinkhow.web.server import create_app

    deps = build_deps(local_env(tmp_path), CARDS)
    client = TestClient(create_app(deps), follow_redirects=False)

    # the person chooses a language first (voice-language S1: a page without one is a 303 to /language)
    chosen = client.post("/language", data={"code": "uk-UA"})
    assert chosen.status_code == 303

    home = client.get("/")
    assert home.status_code == 200
    assert "Усі теми" in home.text and "Мої теми" in home.text

    r = client.post("/topics", data={"title": "Кав'ярня"})
    assert r.status_code == 303
    topic_path = r.headers["location"].split("://", 1)[-1]
    topic_path = topic_path[topic_path.index("/topics/") :]
    uid, topic_id = topic_path.removeprefix("/topics/").split("/")
    assert uid == "local-owner"

    r = client.post(f"{topic_path}/reply", data={"text": "Хочу відкрити кав'ярню."})
    assert r.status_code == 200
    events = sse_events(r.text)
    assert events[0] == ("saved", {"turn": 1})
    assert events[-1] == ("answered", {"turn": 2})
    assert {name for name, _ in events[1:-1]} == {"delta"}
    assert "".join(data["text"] for _, data in events[1:-1]) == LOCAL_REPLY

    assert client.post(f"{topic_path}/close").status_code == 303

    conversation = deps.storage.read("users", f"local-owner/{topic_id}/conversation.md")
    assert conversation is not None
    text = conversation.decode("utf-8")
    assert "<!-- thinkhow:turn 1 user " in text and "<!-- thinkhow:turn 2 model " in text
    assert "<!-- thinkhow:turn 3 " not in text
    assert "<!-- thinkhow:closed 1 " in text
    raw_map = deps.storage.read("users", f"local-owner/{topic_id}/map.json")
    assert raw_map is not None
    assert [item["id"] for item in json.loads(raw_map)["items"]] == ["i1"]


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def test_uvicorn_starts_the_app_in_local_mode_and_home_opens(tmp_path: Path) -> None:
    port = _free_port()
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith("THINKHOW_") and k not in ("K_SERVICE", "CLOUD_RUN_JOB")
    }
    env.update(local_env(tmp_path), PYTHONPATH=str(REPO / "src"))
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "thinkhow.web.app:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=tmp_path,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    try:
        started = False
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline and proc.poll() is None:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/language", timeout=2) as resp:
                    started = resp.status == 200
                break
            except OSError:
                time.sleep(0.2)
        assert started, f"uvicorn did not serve /language (exit {proc.poll()})"

        # the person chooses a language first (voice-language S1), then home opens
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request(
            "POST",
            "/language",
            body="code=uk-UA",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        chosen = conn.getresponse()
        chosen.read()
        conn.close()
        assert chosen.status == 303

        with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=5) as resp:
            status, body = resp.status, resp.read().decode("utf-8")
        assert status == 200, f"uvicorn did not serve / (exit {proc.poll()})"
        assert "Усі теми" in body
    finally:
        proc.terminate()
        try:
            out, _ = proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            out, _ = proc.communicate()
        print(out.decode("utf-8", "replace")[-3000:])
