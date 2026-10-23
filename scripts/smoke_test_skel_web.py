"""Manual smoke of thinkhow.web: uvicorn in local mode on a free port, a topic, a turn over SSE, then stop.

Run: `uv run python scripts/smoke_test_skel_web.py`. Through IAP — only on the owner's deployment (PR-04).
"""

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def main() -> None:
    port, data = free_port(), tempfile.mkdtemp(prefix="thinkhow-smoke-")
    env = {
        **os.environ,
        "PYTHONPATH": str(ROOT / "src"),
        "THINKHOW_LOCAL": "true",
        "THINKHOW_LOCAL_DIR": data,
        "THINKHOW_OWNER_EMAIL": "owner@localhost",
    }
    command = [sys.executable, "-m", "uvicorn", "thinkhow.web.app:app", "--port", str(port)]
    server = subprocess.Popen(command, cwd=ROOT, env=env)
    base = f"http://127.0.0.1:{port}"
    try:
        for _ in range(100):
            try:
                httpx.get(base + "/language")
                break
            except httpx.ConnectError:
                time.sleep(0.1)
        else:
            raise AssertionError("uvicorn did not start")
        chosen = httpx.post(base + "/language", data={"code": "uk-UA"})
        assert chosen.status_code == 303, chosen.status_code
        print("POST /language uk-UA → 303 (F13: a language is chosen before the pages)")
        home = httpx.get(base + "/")
        assert home.status_code == 200 and "Мої теми" in home.text and "Усі теми" in home.text
        print("GET / → 200, «Мої теми», «Усі теми»")
        topic = httpx.post(base + "/topics", data={"title": "Smoke"}).headers["location"]
        with httpx.stream("POST", base + topic + "/reply", data={"text": "Хочу перевірити план."}) as r:
            body = "".join(r.iter_text())
        names = [line.removeprefix("event: ") for line in body.split("\n") if line.startswith("event:")]
        print("SSE events:", names)
        assert names[0] == "saved" and names[-1] == "answered"
        data_lines = [json.loads(line[6:]) for line in body.split("\n") if line.startswith("data: ")]
        print("streamed reply:", "".join(d.get("text", "") for d in data_lines))
        print(f"OK: home, a topic and a streamed answer; the files stay under {data} for a look")
    finally:
        server.terminate()
        server.wait(timeout=10)


if __name__ == "__main__":
    main()
