"""Manual smoke of thinkhow.learning: the Job `seed` and `analyze` as processes, local mode, a temp folder.

Run: `uv run python scripts/smoke_test_skel_learning.py`. The real Job is the owner's deployment (S7).
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def job(command: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    run = [sys.executable, "-m", "thinkhow.learning.job", command]
    return subprocess.run(run, cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)


def main() -> None:
    import importlib

    app_module = importlib.import_module("thinkhow.web.app")
    server = importlib.import_module("thinkhow.web.server")
    data = tempfile.mkdtemp(prefix="thinkhow-learning-")
    env = {
        **os.environ,
        "PYTHONPATH": str(ROOT / "src"),
        "THINKHOW_LOCAL": "true",
        "THINKHOW_LOCAL_DIR": data,
    }
    seeded = job("seed", env)
    print("seed:", seeded.returncode, seeded.stdout.strip())
    assert seeded.returncode == 0
    client = TestClient(server.create_app(app_module.build_deps(env, ROOT / "cards")), follow_redirects=False)
    assert client.post("/language", data={"code": "uk-UA"}).status_code == 303  # F13: language first
    topic = client.post("/topics", data={"title": "Smoke"}).headers["location"]
    client.post(f"{topic}/reply", data={"text": "Хочу перевірити план запуску."})
    first = job("analyze", env)
    print("analyze:", first.returncode, first.stdout.strip())
    assert first.returncode == 0
    uid, topic_id = topic.split("/")[2:4]
    path = Path(data) / "system" / "learning" / "observations" / uid / topic_id / "t1-t2.json"
    observation = json.loads(path.read_text(encoding="utf-8"))
    print("observation:", json.dumps(observation, ensure_ascii=False, indent=2))
    assert f'id="t{observation["turn"]}"' in client.get(topic).text
    second = job("analyze", env)
    done = [json.loads(line) for line in second.stdout.splitlines() if '"analyze_done"' in line][-1]
    print("second analyze:", done)
    assert (done["written"], done["skipped"]) == (0, 1)
    print("OK: seed, analyze → one observation whose link opens an existing turn; a repeat writes nothing")


if __name__ == "__main__":
    main()
